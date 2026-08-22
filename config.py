"""Runtime configuration. Everything is env-overridable so the box can differ from the laptop."""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- MongoDB -------------------------------------------------------------
    # Change streams and multi-document transactions both require a replica set.
    # A single-node replica set is fine; setup_gb10.sh configures one.
    mongo_uri: str = "mongodb://127.0.0.1:27017/?replicaSet=rs0&directConnection=true"
    mongo_db: str = "safecontext"

    # --- Local inference -----------------------------------------------------
    # Planner and triage. Never the external model.
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "nemotron3-nano:30b"
    ollama_timeout_s: float = 120.0
    # Fallbacks tried in order if ollama_model is absent from `ollama list`.
    ollama_fallbacks: str = "nemotron3:30b,nemotron-3-nano-30b,qwen3.6:35b,qwen3.5:9b"

    # --- Stream --------------------------------------------------------------
    stream_rate_hz: float = 8.0
    tier1_score_low: float = 0.35      # below this, Tier 0 clears it
    tier1_score_high: float = 0.75     # above this AND high value -> Tier 2
    tier2_min_amount: float = 5000.0

    # --- Escalation (the only egress) ---------------------------------------
    escalation_enabled: bool = False   # off by default; demo turns it on deliberately
    escalation_url: str = ""
    escalation_model: str = ""
    escalation_api_key: str = ""
    escalation_timeout_s: float = 45.0

    # --- App -----------------------------------------------------------------
    host: str = "127.0.0.1"
    port: int = 8000
    seed_rng: int = 20260822


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()


def data_dir() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "web")
