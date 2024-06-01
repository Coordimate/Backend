#!/bin/bash

docker exec -it backend-mongo-1 mongosh mongodb://127.0.0.1/coordimate -u root -p example --authenticationDatabase admin --eval "db.users.deleteMany({});"
docker exec -it backend-mongo-1 mongosh mongodb://127.0.0.1/coordimate -u root -p example --authenticationDatabase admin --eval "db.meetings.deleteMany({});"
docker exec -it backend-mongo-1 mongosh mongodb://127.0.0.1/coordimate -u root -p example --authenticationDatabase admin --eval "db.groups.deleteMany({});"
docker exec -it backend-web-1 pytest -x tests
