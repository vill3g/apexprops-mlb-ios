"""
MLB Injured List (IL) Client.
Ingests league-wide injury reports across all 30 Major League clubs,
indexing injured players by normalized name and athlete ID to ensure
injured athletes are never displayed in props, lineups, or starting rotations.
"""

import json
import os
import time
import urllib.request
import re
import unicodedata
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

def normalize_name(name: str) -> str:
    """Normalizes player name by stripping accents, punctuation, and casing."""
    if not name:
        return ""
    # Normalize unicode (accents -> ascii equivalents e.g. Sánchez -> Sanchez)
    n = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8')
    n = n.lower()
    # Remove common suffixes and punctuation
    n = re.sub(r'[\.\,\']', '', n)
    n = re.sub(r'\s+(jr|sr|ii|iii|iv)$', '', n)
    return n.strip()

class InjuriesClient:
    """Fetches, caches, and indexes the official MLB Injured List."""

    def __init__(self, cache_file: str = "static/data/injuries.json", cache_ttl: float = 300.0):
        self.cache_file = cache_file
        self.cache_ttl = cache_ttl
        self._injured_by_name: Dict[str, Dict[str, Any]] = {}
        self._injured_by_id: Dict[int, Dict[str, Any]] = {}
        self._team_injuries: List[Dict[str, Any]] = []
        self._last_fetch_time: float = 0.0
        self._load_from_disk()
        # Fetch fresh data if empty or expired
        if not self._injured_by_name or (time.time() - self._last_fetch_time > self.cache_ttl):
            self.refresh_injuries()

    def _load_from_disk(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._team_injuries = data.get("teams", [])
                    self._build_indices(self._team_injuries)
                    self._last_fetch_time = data.get("timestamp_epoch", time.time())
                    logger.info(f"Loaded {len(self._injured_by_name)} injured players from disk cache.")
            except Exception as e:
                logger.warning(f"Failed to read disk cache {self.cache_file}: {e}")

    def _save_to_disk(self):
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            payload = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S ET"),
                "timestamp_epoch": time.time(),
                "total_injured": len(self._injured_by_name),
                "teams": self._team_injuries
            }
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(self._injured_by_name)} injured players to {self.cache_file}.")
        except Exception as e:
            logger.warning(f"Failed to save disk cache {self.cache_file}: {e}")

    def refresh_injuries(self) -> int:
        """Fetches latest league-wide injuries from ESPN API and rebuilds indices."""
        url = "https://site.web.api.espn.com/apis/site/v2/sports/baseball/mlb/injuries"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=6) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    self._team_injuries = data.get("injuries", [])
                    self._build_indices(self._team_injuries)
                    self._last_fetch_time = time.time()
                    self._save_to_disk()
                    return len(self._injured_by_name)
        except Exception as e:
            logger.error(f"Error refreshing injuries from {url}: {e}")
        return len(self._injured_by_name)

    def _build_indices(self, teams: List[Dict[str, Any]]):
        """Builds fast lookup tables by normalized player name and athlete ID."""
        new_by_name = {}
        new_by_id = {}

        for team_obj in teams:
            team_name = team_obj.get("displayName", "")
            team_injuries = team_obj.get("injuries", [])
            for inj in team_injuries:
                ath = inj.get("athlete", {})
                display_name = ath.get("displayName", "")
                if not display_name:
                    continue

                status = str(inj.get("status", "Injured"))
                details = inj.get("details", {})
                injury_type = details.get("type", "")
                injury_detail = details.get("detail", "")
                return_date = details.get("returnDate", "")
                side = details.get("side", "")

                desc = f"{side} {injury_type} {injury_detail}".strip() or status

                # Extract ESPN athlete ID from headshot or link hrefs
                espn_id = None
                hs = ath.get("headshot", {}).get("href", "")
                m = re.search(r"/full/(\d+)\.png", hs)
                if m:
                    try:
                        espn_id = int(m.group(1))
                    except ValueError:
                        pass

                entry = {
                    "name": display_name,
                    "normalized_name": normalize_name(display_name),
                    "id": espn_id,
                    "team": team_name,
                    "position": ath.get("position", {}).get("abbreviation", ""),
                    "status": status,
                    "injury_type": injury_type,
                    "injury_detail": injury_detail,
                    "description": desc,
                    "return_date": return_date
                }

                new_by_name[normalize_name(display_name)] = entry
                if espn_id:
                    new_by_id[espn_id] = entry

        self._injured_by_name = new_by_name
        self._injured_by_id = new_by_id

    def is_injured(self, name: str, athlete_id: Optional[Any] = None) -> bool:
        """
        Returns True if player is actively on the Injured List, Out, or Day-To-Day.
        """
        if not name and not athlete_id:
            return False

        # Check by athlete ID
        if athlete_id is not None:
            try:
                int_id = int(athlete_id)
                if int_id in self._injured_by_id:
                    return True
            except (ValueError, TypeError):
                pass

        # Check by normalized name
        norm = normalize_name(name)
        if norm in self._injured_by_name:
            return True

        # Check partial token match (first and last name)
        tokens = norm.split()
        if len(tokens) >= 2:
            first, last = tokens[0], tokens[-1]
            for inj_norm in self._injured_by_name:
                inj_tokens = inj_norm.split()
                if len(inj_tokens) >= 2 and inj_tokens[0] == first and inj_tokens[-1] == last:
                    return True

        return False

    def get_injury(self, name: str, athlete_id: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """Returns injury details dict if injured, else None."""
        if athlete_id is not None:
            try:
                int_id = int(athlete_id)
                if int_id in self._injured_by_id:
                    return self._injured_by_id[int_id]
            except (ValueError, TypeError):
                pass

        norm = normalize_name(name)
        if norm in self._injured_by_name:
            return self._injured_by_name[norm]

        tokens = norm.split()
        if len(tokens) >= 2:
            first, last = tokens[0], tokens[-1]
            for inj_norm, val in self._injured_by_name.items():
                inj_tokens = inj_norm.split()
                if len(inj_tokens) >= 2 and inj_tokens[0] == first and inj_tokens[-1] == last:
                    return val

        return None

    def get_all_injured(self) -> List[Dict[str, Any]]:
        """Returns list of all currently injured MLB players."""
        return list(self._injured_by_name.values())

    def get_raw_teams(self) -> List[Dict[str, Any]]:
        """Returns raw team injury groupings."""
        return self._team_injuries
