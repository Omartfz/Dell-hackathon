#!/usr/bin/env bash
# MongoDB Community as a single-node replica set.
#
# The replica set is not optional: change streams and multi-document transactions
# both require an oplog, and a standalone mongod has none. A single node is a
# perfectly valid replica set for this purpose.
set -euo pipefail

NAME="${MONGO_CONTAINER:-safecontext-mongo}"
PORT="${MONGO_PORT:-27017}"
IMAGE="${MONGO_IMAGE:-mongo:7}"        # mongo:7 is MongoDB Community Server

echo "==> MongoDB Community, single-node replica set 'rs0'"

if command -v docker >/dev/null 2>&1; then
  if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
    echo "    container '$NAME' exists; starting it"
    docker start "$NAME" >/dev/null
  else
    echo "    pulling $IMAGE for $(uname -m)"
    docker pull --platform linux/arm64 "$IMAGE" 2>/dev/null || docker pull "$IMAGE"
    docker run -d --name "$NAME" --restart unless-stopped \
      -p "${PORT}:27017" "$IMAGE" --replSet rs0 --bind_ip_all >/dev/null
  fi

  echo -n "    waiting for mongod"
  for _ in $(seq 1 40); do
    if docker exec "$NAME" mongosh --quiet --eval 'db.runCommand({ping:1}).ok' >/dev/null 2>&1; then
      break
    fi
    echo -n "."; sleep 1
  done
  echo

  if docker exec "$NAME" mongosh --quiet --eval 'rs.status().ok' >/dev/null 2>&1; then
    echo "    replica set already initiated"
  else
    echo "    running rs.initiate()"
    docker exec "$NAME" mongosh --quiet --eval \
      'rs.initiate({_id:"rs0",members:[{_id:0,host:"127.0.0.1:27017"}]})' >/dev/null
  fi

  echo -n "    waiting for PRIMARY"
  for _ in $(seq 1 40); do
    if [ "$(docker exec "$NAME" mongosh --quiet --eval 'db.hello().isWritablePrimary' 2>/dev/null)" = "true" ]; then
      echo " ok"; break
    fi
    echo -n "."; sleep 1
  done
  echo
  docker exec "$NAME" mongosh --quiet --eval \
    'print("    setName=" + db.hello().setName + " primary=" + db.hello().isWritablePrimary)'
else
  cat <<'MSG'
    docker not found. Native MongoDB Community works too — start mongod with an
    oplog and initiate the set:

      mongod --replSet rs0 --dbpath /var/lib/mongodb --bind_ip 127.0.0.1 &
      mongosh --eval 'rs.initiate({_id:"rs0",members:[{_id:0,host:"127.0.0.1:27017"}]})'
MSG
  exit 1
fi

echo "==> connection string:"
echo "    mongodb://127.0.0.1:${PORT}/?replicaSet=rs0&directConnection=true"
