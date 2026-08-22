"""Mongo connections. Async (motor) drives the app; sync (pymongo) drives scripts.

Change streams and multi-document transactions both need a replica set, which is why
`setup_gb10.sh` starts mongod with `--replSet rs0` and runs `rs.initiate()`. A
standalone mongod will start fine and then fail the moment the stream opens, so we
check for it explicitly and say so rather than dying with a driver error.
"""
from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient
from pymongo.database import Database

from config import settings

_async_client: AsyncIOMotorClient | None = None
_sync_client: MongoClient | None = None


def adb() -> AsyncIOMotorDatabase:
    global _async_client
    if _async_client is None:
        _async_client = AsyncIOMotorClient(
            settings().mongo_uri, tz_aware=True,
            serverSelectionTimeoutMS=1200, connectTimeoutMS=1200)
    return _async_client[settings().mongo_db]


def sdb() -> Database:
    global _sync_client
    if _sync_client is None:
        _sync_client = MongoClient(
            settings().mongo_uri, tz_aware=True,
            serverSelectionTimeoutMS=1200, connectTimeoutMS=1200)
    return _sync_client[settings().mongo_db]


async def replica_set_ready() -> tuple[bool, str]:
    """Change streams and transactions are unavailable without this."""
    try:
        info = await adb().client.admin.command("hello")
    except Exception as exc:  # pragma: no cover - depends on a live server
        return False, f"cannot reach mongod: {exc}"
    if not info.get("setName"):
        return False, (
            "mongod is running standalone. Change streams and transactions need a "
            "replica set — run scripts/setup_mongo.sh, or start mongod with "
            "--replSet rs0 and run rs.initiate()."
        )
    return True, f"replica set '{info['setName']}' primary={info.get('isWritablePrimary')}"


async def close() -> None:
    global _async_client
    if _async_client is not None:
        _async_client.close()
        _async_client = None
