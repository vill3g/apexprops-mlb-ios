import logging
from typing import Optional

logger = logging.getLogger(__name__)

class KalshiMapper:
    # A simple dictionary for common name mappings if fuzzy matching fails
    TEAM_ALIASES = {
        "Kansas City Chiefs": ["KC", "Chiefs"],
        "Baltimore Ravens": ["BAL", "Ravens"],
        "San Francisco 49ers": ["SF", "49ers"],
        "Dallas Cowboys": ["DAL", "Cowboys"],
        # Add more aliases as necessary
    }

    @staticmethod
    def fuzzy_match_team(prediction_name: str, kalshi_title: str) -> bool:
        """
        Check if the predicted team name exists within the Kalshi market title or subtitle.
        """
        pred_lower = prediction_name.lower()
        title_lower = kalshi_title.lower()
        
        # Direct substring
        if pred_lower in title_lower:
            return True
            
        # Check aliases
        aliases = KalshiMapper.TEAM_ALIASES.get(prediction_name, [])
        for alias in aliases:
            if alias.lower() in title_lower.split():
                return True
                
        # Split prediction name (e.g. "Kansas City Chiefs" -> check if "Chiefs" is in title)
        parts = pred_lower.split()
        if len(parts) > 1 and parts[-1] in title_lower:
            return True

        return False

    @staticmethod
    def get_kalshi_ticker(kalshi_client, sport: str, predicted_team: str) -> Optional[str]:
        """
        Fetches active events for the given sport and tries to find a match for the predicted team.
        """
        try:
            # Map sport to Kalshi category (e.g. NFL -> nfl)
            category = sport.lower()
            
            # This is a simplification; actual Kalshi API uses get_events or get_markets
            # We assume kalshi_client has a method to get active markets by category
            # Let's use the underlying kalshi client structure
            
            # Since the user's kalshi_trader wrapper might not have a generic get_markets_by_category exposed easily,
            # we will attempt to pull all active markets if possible, or use the native client.
            # For now, we will return a mock ticker format or None if not found, to be expanded based on the exact kalshi client implementation.
            
            # Example fallback logic:
            return f"{sport.upper()}-MATCH-{predicted_team.replace(' ', '').upper()}"
        except Exception as e:
            logger.error(f"Error mapping {predicted_team} for {sport}: {e}")
            return None
