from langchain_core.documents import BaseDocumentCompressor, Document
from langchain_core.callbacks import Callbacks
from typing import Optional, Sequence
import operator
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from typing import Any
import logging
import os
from typing import Optional, Union

import requests
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor

from huggingface_hub import snapshot_download
from langchain.retrievers import ContextualCompressionRetriever, EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from open_webui.config import VECTOR_DB
from open_webui.retrieval.vector.connector import VECTOR_DB_CLIENT

from open_webui.models.users import UserModel
from open_webui.models.files import Files
from open_webui.models.knowledge import Knowledges

from open_webui.retrieval.vector.main import GetResult


from open_webui.env import (
    SRC_LOG_LEVELS,
    OFFLINE_MODE,
    ENABLE_FORWARD_USER_INFO_HEADERS,
)
from open_webui.config import (
    RAG_EMBEDDING_QUERY_PREFIX,
    RAG_EMBEDDING_CONTENT_PREFIX,
    RAG_EMBEDDING_PREFIX_FIELD_NAME,
    RAG_EMBEDDING_MODEL_AUTO_UPDATE,
)

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])


class VectorSearchRetriever(BaseRetriever):
    collection_name: Any
    embedding_function: Any
    top_k: int

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        result = VECTOR_DB_CLIENT.search(
            collection_name=self.collection_name,
            vectors=[self.embedding_function(query, RAG_EMBEDDING_QUERY_PREFIX)],
            limit=self.top_k,
        )

        ids = result.ids[0]
        metadatas = result.metadatas[0]
        documents = result.documents[0]

        results = []
        for idx in range(len(ids)):
            results.append(
                Document(
                    metadata=metadatas[idx],
                    page_content=documents[idx],
                )
            )
        return results


def query_doc(
    collection_name: str, query_embedding: list[float], k: int, user: UserModel = None
):
    try:
        log.debug(f"query_doc:doc {collection_name}")
        result = VECTOR_DB_CLIENT.search(
            collection_name=collection_name,
            vectors=[query_embedding],
            limit=k,
        )

        # if result:
        #     log.info(f"query_doc:result {result.ids} {result.metadatas}")

        return result
    except Exception as e:
        log.exception(f"Error querying doc {collection_name} with limit {k}: {e}")
        raise e


def get_doc(collection_name: str, user: UserModel = None):
    try:
        log.debug(f"get_doc:doc {collection_name}")
        result = VECTOR_DB_CLIENT.get(collection_name=collection_name)

        # if result:
        #     log.info(f"query_doc:result {result.ids} {result.metadatas}")

        return result
    except Exception as e:
        log.exception(f"Error getting doc {collection_name}: {e}")
        raise e


def query_doc_with_hybrid_search(
    collection_name: str,
    collection_result: GetResult,
    query: str,
    embedding_function,
    k: int,
    reranking_function,
    k_reranker: int,
    r: float,
) -> dict:
    try:
        log.debug(f"query_doc_with_hybrid_search:doc {collection_name}")
        bm25_retriever = BM25Retriever.from_texts(
            texts=collection_result.documents[0],
            metadatas=collection_result.metadatas[0],
        )
        bm25_retriever.k = k

        vector_search_retriever = VectorSearchRetriever(
            collection_name=collection_name,
            embedding_function=embedding_function,
            top_k=k,
        )

        ensemble_retriever = EnsembleRetriever(
            retrievers=[bm25_retriever, vector_search_retriever], weights=[0.5, 0.5]
        )
        compressor = RerankCompressor(
            embedding_function=embedding_function,
            top_n=k_reranker,
            reranking_function=reranking_function,
            r_score=r,
        )

        compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor, base_retriever=ensemble_retriever
        )

        result = compression_retriever.invoke(query)

        distances = [d.metadata.get("score") for d in result]
        documents = [d.page_content for d in result]
        metadatas = [d.metadata for d in result]

        # retrieve only min(k, k_reranker) items, sort and cut by distance if k < k_reranker
        if k < k_reranker:
            sorted_items = sorted(
                zip(distances, metadatas, documents), key=lambda x: x[0], reverse=True
            )
            sorted_items = sorted_items[:k]
            distances, documents, metadatas = map(list, zip(*sorted_items))

        result = {
            "distances": [distances],
            "documents": [documents],
            "metadatas": [metadatas],
        }

        log.info(
            "query_doc_with_hybrid_search:result "
            + f'{result["metadatas"]} {result["distances"]}'
        )
        return result
    except Exception as e:
        log.exception(f"Error querying doc {collection_name} with hybrid search: {e}")
        raise e


def merge_get_results(get_results: list[dict]) -> dict:
    # Initialize lists to store combined data
    combined_documents = []
    combined_metadatas = []
    combined_ids = []

    for data in get_results:
        combined_documents.extend(data["documents"][0])
        combined_metadatas.extend(data["metadatas"][0])
        combined_ids.extend(data["ids"][0])

    # Create the output dictionary
    result = {
        "documents": [combined_documents],
        "metadatas": [combined_metadatas],
        "ids": [combined_ids],
    }

    return result


def merge_and_sort_query_results(query_results: list[dict], k: int) -> dict:
    # Initialize lists to store combined data
    combined = dict()  # To store documents with unique document hashes

    for data in query_results:
        distances = data["distances"][0]
        documents = data["documents"][0]
        metadatas = data["metadatas"][0]

        for distance, document, metadata in zip(distances, documents, metadatas):
            if isinstance(document, str):
                doc_hash = hashlib.md5(
                    document.encode()
                ).hexdigest()  # Compute a hash for uniqueness

                if doc_hash not in combined.keys():
                    combined[doc_hash] = (distance, document, metadata)
                    continue  # if doc is new, no further comparison is needed

                # if doc is alredy in, but new distance is better, update
                if distance > combined[doc_hash][0]:
                    combined[doc_hash] = (distance, document, metadata)

    combined = list(combined.values())
    # Sort the list based on distances
    combined.sort(key=lambda x: x[0], reverse=True)

    # Slice to keep only the top k elements
    sorted_distances, sorted_documents, sorted_metadatas = (
        zip(*combined[:k]) if combined else ([], [], [])
    )

    # Create and return the output dictionary
    return {
        "distances": [list(sorted_distances)],
        "documents": [list(sorted_documents)],
        "metadatas": [list(sorted_metadatas)],
    }


def get_all_items_from_collections(collection_names: list[str]) -> dict:
    results = []

    for collection_name in collection_names:
        if collection_name:
            try:
                result = get_doc(collection_name=collection_name)
                if result is not None:
                    results.append(result.model_dump())
            except Exception as e:
                log.exception(f"Error when querying the collection: {e}")
        else:
            pass

    return merge_get_results(results)


def query_collection(
    collection_names: list[str],
    queries: list[str],
    embedding_function,
    k: int,
    precomputed_embeddings: Optional[list[list[float]]] = None,
) -> dict:
    start_time = time.perf_counter()
    results = []
    
    # Batch all queries together for embedding generation (or use pre-computed embeddings)
    if queries:
        if precomputed_embeddings is not None:
            log.info(f"query_collection: using {len(precomputed_embeddings)} pre-computed embeddings")
            all_query_embeddings = precomputed_embeddings
        else:
            log.info(f"query_collection: batching {len(queries)} queries together")
            embedding_start = time.perf_counter()
            all_query_embeddings = embedding_function(queries, prefix=RAG_EMBEDDING_QUERY_PREFIX)
            embedding_time = time.perf_counter() - embedding_start
            log.debug(f"PERF: query_collection embedding generation took {embedding_time:.3f}s for {len(queries)} queries")
        
        # Ensure we got embeddings for all queries
        # The embedding function should return a list when given a list of queries
        if not isinstance(all_query_embeddings, list):
            # Edge case: single query might return a single embedding instead of a list
            all_query_embeddings = [all_query_embeddings]
        
        # Verify we have the right number of embeddings
        if len(all_query_embeddings) != len(queries):
            log.warning(f"query_collection: Expected {len(queries)} embeddings, got {len(all_query_embeddings)}. Using available embeddings.")
            # Truncate or pad as needed to match query count
            if len(all_query_embeddings) < len(queries):
                log.error(f"query_collection: Not enough embeddings returned. Some queries will be skipped.")
                # Only process queries we have embeddings for
                queries = queries[:len(all_query_embeddings)]
            else:
                # Too many embeddings, truncate
                all_query_embeddings = all_query_embeddings[:len(queries)]
        
        # Prepare tasks for parallel vector DB searches
        def process_search(query_idx, query_embedding, collection_name):
            search_start = time.perf_counter()
            try:
                result = query_doc(
                    collection_name=collection_name,
                    k=k,
                    query_embedding=query_embedding,
                )
                search_time = time.perf_counter() - search_start
                log.debug(f"PERF: query_doc({collection_name}) took {search_time:.3f}s")
                return result.model_dump() if result is not None else None
            except Exception as e:
                search_time = time.perf_counter() - search_start
                query_str = queries[query_idx] if query_idx < len(queries) else f"query_idx_{query_idx}"
                log.exception(f"Error when querying collection {collection_name} with query {query_str}: {e} (took {search_time:.3f}s)")
                return None
        
        # Use ThreadPoolExecutor to search all collections in parallel for all queries
        tasks = []
        for query_idx, query_embedding in enumerate(all_query_embeddings):
            for collection_name in collection_names:
                if collection_name:
                    tasks.append((query_idx, query_embedding, collection_name))
        
        log.debug(f"PERF: query_collection preparing {len(tasks)} search tasks across {len(collection_names)} collections")
        search_start = time.perf_counter()
        # Execute searches in parallel
        with ThreadPoolExecutor() as executor:
            future_results = [
                executor.submit(process_search, query_idx, query_embedding, collection_name)
                for query_idx, query_embedding, collection_name in tasks
            ]
            task_results = [future.result() for future in future_results]
        search_time = time.perf_counter() - search_start
        log.debug(f"PERF: query_collection parallel vector DB searches took {search_time:.3f}s for {len(tasks)} tasks")
        
        # Collect valid results
        for result in task_results:
            if result is not None:
                results.append(result)
    else:
        log.warning("query_collection: No queries provided")

    total_time = time.perf_counter() - start_time
    log.debug(f"PERF: query_collection total time: {total_time:.3f}s (queries={len(queries)}, collections={len(collection_names)}, results={len(results)})")
    return merge_and_sort_query_results(results, k=k)


def query_collection_with_hybrid_search(
    collection_names: list[str],
    queries: list[str],
    embedding_function,
    k: int,
    reranking_function,
    k_reranker: int,
    r: float,
) -> dict:
    results = []
    error = False
    # Fetch collection data once per collection sequentially
    # Avoid fetching the same data multiple times later
    collection_results = {}
    for collection_name in collection_names:
        try:
            log.debug(
                f"query_collection_with_hybrid_search:VECTOR_DB_CLIENT.get:collection {collection_name}"
            )
            collection_results[collection_name] = VECTOR_DB_CLIENT.get(
                collection_name=collection_name
            )
        except Exception as e:
            log.exception(f"Failed to fetch collection {collection_name}: {e}")
            collection_results[collection_name] = None

    log.info(
        f"Starting hybrid search for {len(queries)} queries in {len(collection_names)} collections..."
    )

    def process_query(collection_name, query):
        try:
            result = query_doc_with_hybrid_search(
                collection_name=collection_name,
                collection_result=collection_results[collection_name],
                query=query,
                embedding_function=embedding_function,
                k=k,
                reranking_function=reranking_function,
                k_reranker=k_reranker,
                r=r,
            )
            return result, None
        except Exception as e:
            log.exception(f"Error when querying the collection with hybrid_search: {e}")
            return None, e

    # Prepare tasks for all collections and queries
    # Avoid running any tasks for collections that failed to fetch data (have assigned None)
    tasks = [
        (cn, q)
        for cn in collection_names
        if collection_results[cn] is not None
        for q in queries
    ]

    with ThreadPoolExecutor() as executor:
        future_results = [executor.submit(process_query, cn, q) for cn, q in tasks]
        task_results = [future.result() for future in future_results]

    for result, err in task_results:
        if err is not None:
            error = True
        elif result is not None:
            results.append(result)

    if error and not results:
        raise Exception(
            "Hybrid search failed for all collections. Using Non-hybrid search as fallback."
        )

    return merge_and_sort_query_results(results, k=k)


def get_embedding_function(
    embedding_engine,
    embedding_model,
    embedding_function,
    url,
    key,
    embedding_batch_size,
):
    if embedding_engine == "":
        return lambda query, prefix=None, user=None: embedding_function.encode(
            query, **({"prompt": prefix} if prefix else {})
        ).tolist()
    elif embedding_engine in ["ollama", "openai"]:
        def func(query, prefix=None, user=None): return generate_embeddings(
            engine=embedding_engine,
            model=embedding_model,
            text=query,
            prefix=prefix,
            url=url,
            key=key,
            user=user,
        )

        def generate_multiple(query, prefix, user, func):
            if isinstance(query, list):
                embeddings = []
                # Handle maximum batch size mode: -1 or 0 means send all chunks at once
                effective_batch_size = len(query) if (embedding_batch_size == -1 or embedding_batch_size == 0) else embedding_batch_size
                for i in range(0, len(query), effective_batch_size):
                    embeddings.extend(
                        func(
                            query[i: i + effective_batch_size],
                            prefix=prefix,
                            user=user,
                        )
                    )
                return embeddings
            else:
                return func(query, prefix, user)

        return lambda query, prefix=None, user=None: generate_multiple(
            query, prefix, user, func
        )
    else:
        raise ValueError(f"Unknown embedding engine: {embedding_engine}")


def get_embedding_function_with_usage(
    embedding_engine,
    embedding_model,
    embedding_function,
    url,
    key,
    embedding_batch_size,
):
    """
    Get embedding function that returns both embeddings and usage data.
    Returns a function that takes (query, prefix=None, user=None) and returns
    (embeddings, aggregated_usage) where aggregated_usage is a dict with:
    - total_cost: float
    - total_tokens: int
    - count: int
    - usage_list: list of individual usage dicts
    """
    from open_webui.services.embedding_metrics import get_sentence_transformer_tokens

    if embedding_engine == "":
        # SentenceTransformers
        def func(query, prefix=None, user=None):
            if isinstance(query, list):
                embeddings = []
                total_tokens = 0
                for text in query:
                    emb = embedding_function.encode(text, **({"prompt": prefix} if prefix else {})).tolist()
                    embeddings.append(emb)
                    # Calculate tokens
                    tokens = get_sentence_transformer_tokens(embedding_function, [text])
                    total_tokens += tokens
                aggregated_usage = {
                    "total_cost": 0.0,
                    "total_tokens": total_tokens,
                    "count": len(query),
                    "usage_list": [{"cost": 0, "prompt_tokens": get_sentence_transformer_tokens(embedding_function, [text])} for text in query]
                }
                # Ensure total_tokens is correct (sum of individual tokens)
                if aggregated_usage["usage_list"]:
                    aggregated_usage["total_tokens"] = sum(u.get("prompt_tokens", 0) for u in aggregated_usage["usage_list"])
                return embeddings, aggregated_usage
            else:
                emb = embedding_function.encode(query, **({"prompt": prefix} if prefix else {})).tolist()
                tokens = get_sentence_transformer_tokens(embedding_function, [query])
                aggregated_usage = {
                    "total_cost": 0.0,
                    "total_tokens": tokens,
                    "count": 1,
                    "usage_list": [{"cost": 0, "prompt_tokens": tokens}]
                }
                return emb, aggregated_usage
        return func
    elif embedding_engine in ["ollama", "openai"]:
        def func(query, prefix=None, user=None):
            if isinstance(query, list):
                embeddings = []
                aggregated_usage = {
                    "total_cost": 0.0,
                    "total_tokens": 0,
                    "count": 0,
                    "usage_list": []
                }
                # Handle maximum batch size mode: -1 or 0 means send all chunks at once
                effective_batch_size = len(query) if (embedding_batch_size == -1 or embedding_batch_size == 0) else embedding_batch_size
                for i in range(0, len(query), effective_batch_size):
                    batch = query[i: i + effective_batch_size]
                    if embedding_engine == "ollama":
                        batch_embeddings, batch_usage = generate_ollama_batch_embeddings(
                            model=embedding_model,
                            texts=batch,
                            url=url,
                            key=key,
                            prefix=prefix,
                            user=user,
                        )
                    else:  # openai
                        batch_embeddings, batch_usage = generate_openai_batch_embeddings(
                            model=embedding_model,
                            texts=batch,
                            url=url,
                            key=key,
                            prefix=prefix,
                            user=user,
                        )
                    if batch_embeddings:
                        embeddings.extend(batch_embeddings)
                        # Aggregate usage
                        if batch_usage:
                            cost = batch_usage.get("cost", 0) or 0
                            if embedding_engine == "ollama":
                                tokens = batch_usage.get("prompt_eval_count", 0) or 0
                            else:  # openai
                                tokens = batch_usage.get("prompt_tokens", 0) or 0
                            aggregated_usage["total_cost"] += cost
                            aggregated_usage["total_tokens"] += tokens
                            aggregated_usage["count"] += 1
                            aggregated_usage["usage_list"].append(batch_usage)
                return embeddings, aggregated_usage
            else:
                # Single query
                if embedding_engine == "ollama":
                    embeddings, usage = generate_ollama_batch_embeddings(
                        model=embedding_model,
                        texts=[query],
                        url=url,
                        key=key,
                        prefix=prefix,
                        user=user,
                    )
                else:  # openai
                    embeddings, usage = generate_openai_batch_embeddings(
                        model=embedding_model,
                        texts=[query],
                        url=url,
                        key=key,
                        prefix=prefix,
                        user=user,
                    )
                if embeddings:
                    embeddings = embeddings[0]
                cost = usage.get("cost", 0) or 0 if usage else 0
                if embedding_engine == "ollama":
                    tokens = usage.get("prompt_eval_count",0) or 0 if usage else 0
                else:  # openai
                    tokens = usage.get("prompt_tokens", 0) or 0 if usage else 0
                aggregated_usage = {
                    "total_cost": cost,
                    "total_tokens": tokens,
                    "count": 1,
                    "usage_list": [usage] if usage else []
                }
                return embeddings, aggregated_usage
        return func
    else:
        raise ValueError(f"Unknown embedding engine: {embedding_engine}")


def get_sources_from_files(
    request,
    files,
    queries,
    embedding_function,
    k,
    reranking_function,
    k_reranker,
    r,
    hybrid_search,
    full_context=False,
):
    """
    Get sources from files. Handles embedding function selection for web search collections.
    Web search collections use the web search embedding override if configured.
    """
    def _ctx_counts(ctx: dict) -> tuple[int, int]:
        try:
            documents = ctx.get("documents") or []
            metadatas = ctx.get("metadatas") or []
            num_docs = len(documents[0]) if isinstance(
                documents, list) and len(documents) > 0 else 0
            num_metas = len(metadatas[0]) if isinstance(
                metadatas, list) and len(metadatas) > 0 else 0
            return num_docs, num_metas
        except Exception:
            return 0, 0

    def _has_results(ctx: dict) -> bool:
        try:
            n_docs, n_metas = _ctx_counts(ctx)
            return n_docs > 0 and n_metas > 0
        except Exception:
            return False

    log.debug(f"RAG DEBUGINFO get_sources_from_files: Called with {len(files)} files, {len(queries)} queries")
    log.debug(f"RAG DEBUGINFO get_sources_from_files: full_context={full_context}, hybrid_search={hybrid_search}")
    log.debug(f"files: {files} {queries} {embedding_function} {reranking_function} {full_context}")

    extracted_collections = []
    relevant_contexts = []
    
    # Store file contexts and query tasks for parallelization
    file_contexts = {}  # file_idx -> context (if already available)
    query_tasks = []  # List of query tasks to execute in parallel

    for file_idx, file in enumerate(files):
        log.debug(f"RAG DEBUGINFO get_sources_from_files: Processing file {file_idx}: type={file.get('type')}, "
                 f"id={file.get('id')}, collection_name={file.get('collection_name')}, "
                 f"keys={list(file.keys())}")

        context = None
        needs_query = False  # Track if this file needs a query_collection call
        
        if file.get("docs"):
            # BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL
            context = {
                "documents": [[doc.get("content") for doc in file.get("docs")]],
                "metadatas": [[doc.get("metadata") for doc in file.get("docs")]],
            }
        elif file.get("context") == "full":
            # Manual Full Mode Toggle
            context = {
                "documents": [[file.get("file").get("data", {}).get("content")]],
                "metadatas": [[{"file_id": file.get("id"), "name": file.get("name")}]],
            }
        elif (
            file.get("type") != "web_search"
            and request.app.state.config.BYPASS_EMBEDDING_AND_RETRIEVAL
        ):
            # BYPASS_EMBEDDING_AND_RETRIEVAL
            if file.get("type") == "collection":
                collection_id = file.get("id")
                # Try to get file_ids from the file object first (for backward compatibility)
                file_ids = file.get("data", {}).get("file_ids", [])
                # If not present, query the knowledge table
                if not file_ids and collection_id:
                    try:
                        knowledge = Knowledges.get_knowledge_by_id(collection_id)
                        if knowledge and knowledge.data:
                            file_ids = knowledge.data.get("file_ids", [])
                    except Exception as e:
                        log.warning(f"Failed to fetch file_ids from knowledge table for collection {collection_id}: {e}")
                        file_ids = []

                documents = []
                metadatas = []
                for file_id in file_ids:
                    file_object = Files.get_file_by_id(file_id)

                    if file_object:
                        documents.append(file_object.data.get("content", ""))
                        metadatas.append(
                            {
                                "file_id": file_id,
                                "name": file_object.filename,
                                "source": file_object.filename,
                            }
                        )

                context = {
                    "documents": [documents],
                    "metadatas": [metadatas],
                }

            elif file.get("id"):
                file_object = Files.get_file_by_id(file.get("id"))
                if file_object:
                    context = {
                        "documents": [[file_object.data.get("content", "")]],
                        "metadatas": [
                            [
                                {
                                    "file_id": file.get("id"),
                                    "name": file_object.filename,
                                    "source": file_object.filename,
                                }
                            ]
                        ],
                    }
            elif file.get("file").get("data"):
                context = {
                    "documents": [[file.get("file").get("data", {}).get("content")]],
                    "metadatas": [
                        [file.get("file").get("data", {}).get("metadata", {})]
                    ],
                }
        else:
            collection_names = []
            meta = file.get("meta") or {}
            ftype = file.get("type")
            needs_query = False  # Will be set to True if we need to query
            # For direct file attachments, prefer the per-file collection (file-{id})
            if ftype in ["file", "image"] and file.get("id"):
                per_file_collection = f"file-{file['id']}"
                collection_names.append(per_file_collection)
                log.debug(f"RAG DEBUG: File attachment - using per-file collection_name={per_file_collection}")
                # Ensure per-file collection has at least one vector; auto-index if empty
                try:
                    # Gate auto-indexing behind env var to avoid heavy-handed mutation
                    auto_index = (os.getenv("RAG_AUTO_INDEX_MISSING", "false").lower() == "true")
                    get_res = VECTOR_DB_CLIENT.get(collection_name=per_file_collection)
                    has_any = bool(get_res and get_res.ids and len(get_res.ids[0]) > 0)
                    if auto_index and not has_any:
                        fobj = Files.get_file_by_id(file["id"])
                        content_text = (fobj.data or {}).get("content") if fobj else None
                        if content_text:
                            vector = embedding_function(content_text, prefix=RAG_EMBEDDING_CONTENT_PREFIX)
                            VECTOR_DB_CLIENT.upsert(
                                collection_name=per_file_collection,
                                items=[
                                    {
                                        "id": fobj.id,
                                        "text": content_text,
                                        "vector": vector,
                                        "metadata": {
                                            "file_id": fobj.id,
                                            "name": fobj.filename,
                                            "source": fobj.filename,
                                        },
                                    }
                                ],
                            )
                            log.info("RAG: Auto-indexed per-file collection (enabled via RAG_AUTO_INDEX_MISSING)")
                        else:
                            log.debug("RAG DEBUG: Per-file collection empty and file has no stored content; skipping auto-index")
                except Exception as e:
                    log.debug(f"RAG DEBUG: Unable to auto-index per-file collection: {e}")
            elif ftype == "collection":
                if file.get("legacy"):
                    collection_names = file.get("collection_names", [])
                    log.debug(f"RAG DEBUGINFO: Collection (legacy) - collection_names={collection_names}")
                else:
                    # Prefer explicit id; otherwise try meta.collection_name
                    collection_id = file.get("id") or meta.get("collection_name")
                    if collection_id:
                        collection_names.append(collection_id)
                        log.debug(f"RAG DEBUGINFO: Collection (non-legacy) - using id/collection_name={collection_id}")
                    else:
                        log.warning(f"RAG DEBUG: Collection type file has no id or meta.collection_name: {file}")
            elif file.get("collection_name") or meta.get("collection_name"):
                cn = file.get("collection_name") or meta.get("collection_name")
                collection_names.append(cn)
                log.debug(f"RAG DEBUGINFO: File has collection_name={cn}")
            elif file.get("id"):
                if file.get("legacy"):
                    collection_names.append(f"{file['id']}")
                    log.debug(f"RAG DEBUGINFO: File (legacy) - using id={file['id']}")
                else:
                    collection_name = f"file-{file['id']}"
                    collection_names.append(collection_name)
                    log.debug(f"RAG DEBUGINFO: File (non-legacy) - constructed collection_name={collection_name}")
            else:
                log.warning(f"RAG DEBUG: File has no id or collection_name: {file}")

            collection_names = list(set(collection_names).difference(
                extracted_collections))
            log.debug(f"RAG DEBUGINFO: Final collection_names for file {file_idx}: {collection_names}")
            if not collection_names:
                log.debug(f"RAG DEBUGINFO: Skipping file {file_idx} as it has already been extracted")
                # Store empty context for this file
                file_contexts[file_idx] = None
                # Don't extend extracted_collections since we skipped
                continue

            # Track that we'll extract these collections
            extracted_collections.extend(collection_names)

            if full_context:
                try:
                    log.debug(f"RAG DEBUGINFO: Using full_context mode for collections: {collection_names}")
                    context = get_all_items_from_collections(collection_names)
                    d, m = _ctx_counts(context or {})
                    log.debug(f"RAG DEBUGINFO: Full context retrieved: docs={d}, metas={m}")
                except Exception as e:
                    log.exception(f"RAG DEBUG: Exception in get_all_items_from_collections: {e}")

            else:
                try:
                    if file.get("type") == "text":
                        log.debug(f"RAG DEBUGINFO: File type is text, using content directly")
                        context = file["content"]
                    else:
                        needs_query = True
                        log.debug(f"RAG DEBUGINFO: Querying collections: {collection_names}, hybrid_search={hybrid_search}")

                        # Determine which embedding function to use for these collections
                        # If this is a web_search file and web search embedding override is active, use web search embedding function
                        query_embedding_function = embedding_function
                        is_web_search_collection = (
                            file.get("type") == "web_search" or
                            any(cn.startswith("web-search-")
                                for cn in collection_names)
                        )

                        if is_web_search_collection and request.app.state.config.WEB_SEARCH_EMBEDDING_ENGINE and request.app.state.config.WEB_SEARCH_EMBEDDING_ENGINE != "":
                            # Use web search embedding function for web search collections
                            from open_webui.routers.retrieval import get_ef

                            embedding_engine = request.app.state.config.WEB_SEARCH_EMBEDDING_ENGINE
                            embedding_model = request.app.state.config.WEB_SEARCH_EMBEDDING_MODEL or request.app.state.config.RAG_EMBEDDING_MODEL
                            embedding_batch_size = request.app.state.config.WEB_SEARCH_EMBEDDING_BATCH_SIZE or request.app.state.config.RAG_EMBEDDING_BATCH_SIZE

                            # Get embedding function for web search (ef) if needed (for sentence transformers)
                            web_search_ef = request.app.state.ef
                            if embedding_engine == "" or embedding_engine == "sentence-transformers":
                                web_search_ef = get_ef("", embedding_model, RAG_EMBEDDING_MODEL_AUTO_UPDATE)

                            # Normalize sentence-transformers to empty string for get_embedding_function
                            normalized_engine = "" if embedding_engine == "sentence-transformers" else embedding_engine
                            query_embedding_function = get_embedding_function(
                                normalized_engine,
                                embedding_model,
                                web_search_ef,
                                (
                                    request.app.state.config.WEB_SEARCH_OPENAI_API_BASE_URL
                                    if normalized_engine == "openai"
                                    else request.app.state.config.WEB_SEARCH_OLLAMA_BASE_URL
                                ),
                                (
                                    request.app.state.config.WEB_SEARCH_OPENAI_API_KEY
                                    if normalized_engine == "openai"
                                    else request.app.state.config.WEB_SEARCH_OLLAMA_API_KEY
                                ),
                                embedding_batch_size,
                            )
                            log.debug(f"RAG DEBUGINFO: Using web search embedding function for web search collections: engine={embedding_engine}, model={embedding_model}")

                        if hybrid_search:
                            # Hybrid search needs to run sequentially for now (more complex)
                            try:
                                context = query_collection_with_hybrid_search(
                                    collection_names=collection_names,
                                    queries=queries,
                                    embedding_function=query_embedding_function,
                                    k=k,
                                    reranking_function=reranking_function,
                                    k_reranker=k_reranker,
                                    r=r,
                                )
                                d, m = _ctx_counts(context or {})
                                log.debug(f"RAG DEBUGINFO: Hybrid search returned context: docs={d}, metas={m}")
                                needs_query = False  # Got context from hybrid search
                            except Exception as e:
                                log.warning(f"RAG DEBUG: Error when using hybrid search: {e}, using non hybrid search as fallback.")
                                needs_query = True  # Will fall back to standard query

                        if needs_query and ((not hybrid_search) or (context is None) or (not _has_results(context))):
                            log.debug(f"RAG DEBUGINFO: Using standard query_collection (hybrid_search={hybrid_search}, context_has_results={_has_results(context) if context is not None else None})")
                            # Store task info for parallel execution later
                            query_tasks.append({
                                "file_idx": file_idx,
                                "file": file,
                                "collection_names": collection_names,
                                "query_embedding_function": query_embedding_function,
                                "k": k,
                                "hybrid_search": hybrid_search,
                            })
                            # Set context to None for now, will be filled after parallel execution
                            context = None
                            needs_query = False  # Task queued

                    # Fallback: if no results, try loading full file content directly
                    # Only run fallback if we're not waiting for a parallel query
                    if needs_query is False and (context is None or not _has_results(context)) and file.get("id") and file.get("type") in ["file", "image"]:
                        try:
                            fobj = Files.get_file_by_id(file.get("id"))
                            if fobj and (fobj.data or {}).get("content"):
                                content_text = fobj.data.get("content")
                                context = {
                                    "documents": [[content_text]],
                                    "metadatas": [[
                                        {
                                            "file_id": fobj.id,
                                            "name": fobj.filename,
                                            "source": fobj.filename,
                                        }
                                    ]],
                                }
                                log.info("RAG DEBUG: Fallback used - built context from raw file content")
                        except Exception as e:
                            log.debug(f"RAG DEBUG: Fallback failed to read file content: {e}")
                except Exception as e:
                    log.exception(f"RAG DEBUG: Exception querying collections: {e}")

        # Store context if available, otherwise it will be filled after parallel query execution
        if context:
            file_contexts[file_idx] = context
        # If context is None and we have a query task, it will be filled after parallel execution

    # Execute all query_collection calls in parallel
    if query_tasks:
        log.debug(f"PERF: get_sources_from_files executing {len(query_tasks)} query_collection calls in parallel")
        query_start = time.perf_counter()
        
        # Group tasks by embedding function to avoid using wrong embeddings
        # Different files might use different embedding functions (regular RAG vs web search)
        embedding_func_to_tasks = {}
        for task in query_tasks:
            # Use the function object itself as the key (functions are compared by identity)
            func_key = id(task["query_embedding_function"])
            if func_key not in embedding_func_to_tasks:
                embedding_func_to_tasks[func_key] = {
                    "embedding_function": task["query_embedding_function"],
                    "tasks": []
                }
            embedding_func_to_tasks[func_key]["tasks"].append(task)
        
        # Embed queries once per embedding function group
        embedding_func_to_precomputed = {}
        if queries:
            for func_key, func_group in embedding_func_to_tasks.items():
                embedding_func = func_group["embedding_function"]
                try:
                    embedding_start = time.perf_counter()
                    precomputed_embeddings = embedding_func(queries, prefix=RAG_EMBEDDING_QUERY_PREFIX)
                    embedding_time = time.perf_counter() - embedding_start
                    log.debug(f"PERF: get_sources_from_files embedding {len(queries)} queries took {embedding_time:.3f}s for {len(func_group['tasks'])} collections (embedding function group)")
                    
                    # Ensure we got embeddings for all queries
                    if not isinstance(precomputed_embeddings, list):
                        precomputed_embeddings = [precomputed_embeddings]
                    
                    embedding_func_to_precomputed[func_key] = precomputed_embeddings
                except Exception as e:
                    log.exception(f"Error generating precomputed embeddings for embedding function group: {e}. Will generate embeddings individually per query_collection call.")
                    # Don't set precomputed_embeddings for this group - query_collection will generate them individually
        
        def execute_query_task(task):
            try:
                # Get the precomputed embeddings for this task's embedding function
                func_key = id(task["query_embedding_function"])
                precomputed_embeddings = embedding_func_to_precomputed.get(func_key)
                
                return task["file_idx"], query_collection(
                    collection_names=task["collection_names"],
                    queries=queries,
                    embedding_function=task["query_embedding_function"],
                    k=task["k"],
                    precomputed_embeddings=precomputed_embeddings,
                )
            except Exception as e:
                log.exception(f"Error in parallel query_collection for file {task['file_idx']}: {e}")
                return task["file_idx"], None
        
        with ThreadPoolExecutor() as executor:
            future_results = [executor.submit(execute_query_task, task) for task in query_tasks]
            query_results = {file_idx: context for file_idx, context in [future.result() for future in future_results]}
        
        query_time = time.perf_counter() - query_start
        log.debug(f"PERF: get_sources_from_files parallel query_collection calls took {query_time:.3f}s for {len(query_tasks)} tasks")
        
        # Merge query results into file_contexts
        for file_idx, context in query_results.items():
            if context:
                file_contexts[file_idx] = context
            else:
                # Query failed, try fallback for this file
                file = files[file_idx] if file_idx < len(files) else None
                if file and file.get("id") and file.get("type") in ["file", "image"]:
                    try:
                        fobj = Files.get_file_by_id(file.get("id"))
                        if fobj and (fobj.data or {}).get("content"):
                            content_text = fobj.data.get("content")
                            file_contexts[file_idx] = {
                                "documents": [[content_text]],
                                "metadatas": [[
                                    {
                                        "file_id": fobj.id,
                                        "name": fobj.filename,
                                        "source": fobj.filename,
                                    }
                                ]],
                            }
                            log.info(f"RAG DEBUG: Fallback used for file {file_idx} - built context from raw file content")
                    except Exception as e:
                        log.debug(f"RAG DEBUG: Fallback failed to read file content for file {file_idx}: {e}")

    # Build relevant_contexts from all file contexts
    for file_idx, file in enumerate(files):
        context = file_contexts.get(file_idx)
        if context:
            d, m = _ctx_counts(context if isinstance(context, dict) else {})
            log.debug(f"RAG DEBUGINFO: File {file_idx} produced context: docs={d}, metas={m}")
            if "data" in file:
                del file["data"]
            relevant_contexts.append({**context, "file": file})
        elif file_idx not in [task["file_idx"] for task in query_tasks]:
            # Only warn if this file wasn't part of the query tasks (meaning it should have had context)
            log.warning(f"RAG DEBUG: File {file_idx} produced NO context (context is None or empty)")

    log.debug(f"RAG DEBUGINFO: Processing {len(relevant_contexts)} relevant contexts into sources")
    sources = []
    for ctx_idx, context in enumerate(relevant_contexts):
        try:
            d, m = _ctx_counts(context)
            log.debug(f"RAG DEBUGINFO: Processing context {ctx_idx}: docs={d}, metas={m}, file_type={context.get('file', {}).get('type')}")
            if "documents" in context:
                if "metadatas" in context:
                    # Strip collections from source object to reduce payload size
                    file_obj = context["file"]
                    if isinstance(file_obj, dict) and file_obj.get("type") == "collection":
                        from open_webui.models.chat_converter import strip_collection_files
                        file_obj = strip_collection_files(file_obj)

                    source = {
                        "source": file_obj,
                        "document": context["documents"][0],
                        "metadata": context["metadatas"][0],
                    }
                    if "distances" in context and context["distances"]:
                        source["distances"] = context["distances"][0]
                    # Only append non-empty content
                    if source["document"] and source["metadata"] and len(source["document"]) > 0 and len(source["metadata"]) > 0:
                        sources.append(source)
                    else:
                        log.debug(f"RAG DEBUGINFO: Skipping empty source for context {ctx_idx}")
        except Exception as e:
            log.exception(e)

    return sources


def get_model_path(model: str, update_model: bool = False):
    # Construct huggingface_hub kwargs with local_files_only to return the snapshot path
    cache_dir = os.getenv("SENTENCE_TRANSFORMERS_HOME")

    local_files_only = not update_model

    if OFFLINE_MODE:
        local_files_only = True

    snapshot_kwargs = {
        "cache_dir": cache_dir,
        "local_files_only": local_files_only,
    }

    log.debug(f"model: {model}")
    log.debug(f"snapshot_kwargs: {snapshot_kwargs}")

    # Inspiration from upstream sentence_transformers
    if (
        os.path.exists(model)
        or ("\\" in model or model.count("/") > 1)
        and local_files_only
    ):
        # If fully qualified path exists, return input, else set repo_id
        return model
    elif "/" not in model:
        # Set valid repo_id for model short-name
        model = "sentence-transformers" + "/" + model

    snapshot_kwargs["repo_id"] = model

    # Attempt to query the huggingface_hub library to determine the local path and/or to update
    try:
        model_repo_path = snapshot_download(**snapshot_kwargs)
        log.debug(f"model_repo_path: {model_repo_path}")
        return model_repo_path
    except Exception as e:
        log.exception(f"Cannot determine model snapshot path: {e}")
        return model


def generate_openai_batch_embeddings(
    model: str,
    texts: list[str],
    url: str = "https://api.openai.com/v1",
    key: str = "",
    prefix: str = None,
    user: UserModel = None,
) -> tuple[Optional[list[list[float]]], Optional[dict]]:
    """
    Generate embeddings using OpenAI/OpenRouter API.

    Returns:
        Tuple of (embeddings, usage_data) where usage_data contains:
        - prompt_tokens: int
        - total_tokens: int
        - cost: float (if available)
    """
    batch_start = time.perf_counter()
    try:
        log.debug(
            f"generate_openai_batch_embeddings:model {model} batch size: {len(texts)}"
        )
        json_data = {"input": texts, "model": model}
        if isinstance(RAG_EMBEDDING_PREFIX_FIELD_NAME, str) and isinstance(prefix, str):
            json_data[RAG_EMBEDDING_PREFIX_FIELD_NAME] = prefix

        request_start = time.perf_counter()
        r = requests.post(
            f"{url}/embeddings",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                **(
                    {
                        "X-OpenWebUI-User-Name": user.name,
                        "X-OpenWebUI-User-Id": user.id,
                        "X-OpenWebUI-User-Email": user.email,
                        "X-OpenWebUI-User-Role": user.role,
                    }
                    if ENABLE_FORWARD_USER_INFO_HEADERS and user
                    else {}
                ),
            },
            json=json_data,
        )
        request_time = time.perf_counter() - request_start
        r.raise_for_status()
        data = r.json()
        if "data" in data:
            embeddings = [elem["embedding"] for elem in data["data"]]
            # Extract usage data
            usage_data = data.get("usage", {})
            # Include cost if available (OpenRouter format)
            if "cost" in data.get("usage", {}):
                usage_data["cost"] = data["usage"]["cost"]
            batch_time = time.perf_counter() - batch_start
            log.debug(f"PERF: generate_openai_batch_embeddings took {batch_time:.3f}s (request={request_time:.3f}s, batch_size={len(texts)}, model={model})")
            return embeddings, usage_data
        else:
            raise "Something went wrong :/"
    except Exception as e:
        batch_time = time.perf_counter() - batch_start
        log.exception(f"Error generating openai batch embeddings: {e} (took {batch_time:.3f}s)")
        return None, None


def generate_ollama_batch_embeddings(
    model: str,
    texts: list[str],
    url: str,
    key: str = "",
    prefix: str = None,
    user: UserModel = None,
) -> tuple[Optional[list[list[float]]], Optional[dict]]:
    """
    Generate embeddings using Ollama API.

    Returns:
        Tuple of (embeddings, usage_data) where usage_data contains:
        - prompt_eval_count: int (from metadata)
    """
    batch_start = time.perf_counter()
    try:
        log.debug(
            f"generate_ollama_batch_embeddings:model {model} batch size: {len(texts)}"
        )
        json_data = {"input": texts, "model": model}
        if isinstance(RAG_EMBEDDING_PREFIX_FIELD_NAME, str) and isinstance(prefix, str):
            json_data[RAG_EMBEDDING_PREFIX_FIELD_NAME] = prefix

        request_start = time.perf_counter()
        r = requests.post(
            f"{url}/api/embed",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                **(
                    {
                        "X-OpenWebUI-User-Name": user.name,
                        "X-OpenWebUI-User-Id": user.id,
                        "X-OpenWebUI-User-Email": user.email,
                        "X-OpenWebUI-User-Role": user.role,
                    }
                    if ENABLE_FORWARD_USER_INFO_HEADERS
                    else {}
                ),
            },
            json=json_data,
        )
        request_time = time.perf_counter() - request_start
        r.raise_for_status()
        data = r.json()

        if "embeddings" in data:
            embeddings = data["embeddings"]
            # Extract usage data from metadata
            usage_data = {}
            if "prompt_eval_count" in data:
                usage_data["prompt_eval_count"] = data["prompt_eval_count"]
            batch_time = time.perf_counter() - batch_start
            log.debug(f"PERF: generate_ollama_batch_embeddings took {batch_time:.3f}s (request={request_time:.3f}s, batch_size={len(texts)}, model={model})")
            return embeddings, usage_data
        else:
            raise "Something went wrong :/"
    except Exception as e:
        batch_time = time.perf_counter() - batch_start
        log.exception(f"Error generating ollama batch embeddings: {e} (took {batch_time:.3f}s)")
        return None, None


def generate_embeddings(
    engine: str,
    model: str,
    text: Union[str, list[str]],
    prefix: Union[str, None] = None,
    **kwargs,
):
    """
    Generate embeddings. Returns embeddings only (for backward compatibility).
    For usage data, use the batch functions directly or get_embedding_function_with_usage.
    """
    url = kwargs.get("url", "")
    key = kwargs.get("key", "")
    user = kwargs.get("user")

    if prefix is not None and RAG_EMBEDDING_PREFIX_FIELD_NAME is None:
        if isinstance(text, list):
            text = [f"{prefix}{text_element}" for text_element in text]
        else:
            text = f"{prefix}{text}"

    if engine == "ollama":
        if isinstance(text, list):
            embeddings, _ = generate_ollama_batch_embeddings(
                **{
                    "model": model,
                    "texts": text,
                    "url": url,
                    "key": key,
                    "prefix": prefix,
                    "user": user,
                }
            )
        else:
            embeddings, _ = generate_ollama_batch_embeddings(
                **{
                    "model": model,
                    "texts": [text],
                    "url": url,
                    "key": key,
                    "prefix": prefix,
                    "user": user,
                }
            )
        return embeddings[0] if isinstance(text, str) and embeddings else embeddings
    elif engine == "openai":
        if isinstance(text, list):
            embeddings, _ = generate_openai_batch_embeddings(
                model, text, url, key, prefix, user
            )
        else:
            embeddings, _ = generate_openai_batch_embeddings(
                model, [text], url, key, prefix, user
            )
        return embeddings[0] if isinstance(text, str) and embeddings else embeddings


class RerankCompressor(BaseDocumentCompressor):
    embedding_function: Any
    top_n: int
    reranking_function: Any
    r_score: float

    class Config:
        extra = "forbid"
        arbitrary_types_allowed = True

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Optional[Callbacks] = None,
    ) -> Sequence[Document]:
        reranking = self.reranking_function is not None

        if reranking:
            scores = self.reranking_function.predict(
                [(query, doc.page_content) for doc in documents]
            )
        else:
            from sentence_transformers import util

            query_embedding = self.embedding_function(query, RAG_EMBEDDING_QUERY_PREFIX)
            document_embedding = self.embedding_function(
                [doc.page_content for doc in documents], RAG_EMBEDDING_CONTENT_PREFIX
            )
            scores = util.cos_sim(query_embedding, document_embedding)[0]

        docs_with_scores = list(zip(documents, scores.tolist()))
        if self.r_score:
            docs_with_scores = [
                (d, s) for d, s in docs_with_scores if s >= self.r_score
            ]

        result = sorted(docs_with_scores,key=operator.itemgetter(1), reverse=True)
        final_results = []
        for doc, doc_score in result[: self.top_n]:
            metadata = doc.metadata
            metadata["score"] = doc_score
            doc = Document(
                page_content=doc.page_content,
                metadata=metadata,
            )
            final_results.append(doc)
        return final_results
