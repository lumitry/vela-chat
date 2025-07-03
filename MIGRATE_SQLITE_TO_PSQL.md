# how 2 migrate from sqlite to postgresql

1. export your database (can be done in admin settings, or probably via docker exec -it <container_name> bash and then copying it over or something, IDK)
2. set up a postgres database (e.g. using docker)
3. change your DB URL env var to point to the new postgres database, e.g. `DATABASE_URL=postgres://user:password@localhost/dbname`
4. run the application to create the necessary tables in the new database (then stop the app)
5. run the migrate script:
   ```bash
   chmod +x migrate.sh
   ./migrate.sh
   ```
6. run the application again, it should now be using the new postgres database with all your data migrated from sqlite