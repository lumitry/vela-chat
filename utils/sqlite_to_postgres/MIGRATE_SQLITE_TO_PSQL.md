# how 2 migrate from sqlite to postgresql

1. export your sqlite database (can be done in admin settings, or `docker cp <container_name>:/app/backend/data/webui.db /path/on/host/webui.db`)
2. set up an empty postgres database (e.g. using docker)
3. change your DB URL env var to point to the new postgres database, e.g. `DATABASE_URL=postgres://user:password@localhost/dbname`
4. run the application to create the necessary tables in the new database (then stop the app)
5. run the migrate script (can be found in the root directory of this repo):
   ```bash
   chmod +x migrate.sh
   ./migrate.sh
   ```
   (this should read your DATABASE_URL from the `.env` file if it exists (or use a default otherwise), but you may need to modify the script if you get issues, especially if you're running the script on a different machine than the one where the app is running)
6. run the application again, it should now be using the new postgres database with all your data migrated from sqlite
7. remember to delete the massive `pg_dump/` directory that was created when the script ran, unless you want to keep it for some reason