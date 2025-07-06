# how 2 migrate from sqlite to postgresql

1. export your database (can be done in admin settings, or `docker cp <container_name>:/app/backend/data/webui.db /path/on/host/webui.db`)
2. set up a postgres database (e.g. using docker)
3. change your DB URL env var to point to the new postgres database, e.g. `DATABASE_URL=postgres://user:password@localhost/dbname`
4. run the application to create the necessary tables in the new database (then stop the app)
5. run the migrate script (can be found in the root directory of this repo):
   ```bash
   chmod +x migrate.sh
   ./migrate.sh
   ```
   (note: you may need to adjust the script to match your env; at the moment, it does not load your database from the env var, for example.)
6. run the application again, it should now be using the new postgres database with all your data migrated from sqlite
7. remember to delete the massive `pg_dump/` directory that was created when the script ran, unless you want to keep it for some reason