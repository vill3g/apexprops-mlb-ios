import os
import json
from typing import Optional, Dict, Any

REGISTRY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'player_photos_registry.json')

class PlayerPhotoResolver:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PlayerPhotoResolver, cls).__new__(cls)
            cls._instance._init_resolver()
        return cls._instance

    def _init_resolver(self):
        self.registry: Dict[str, Dict[str, Any]] = {}
        self._load_registry()

    def _load_registry(self):
        if os.path.exists(REGISTRY_PATH):
            try:
                with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
                    self.registry = json.load(f)
            except Exception as e:
                print(f'Error loading player photo registry: {e}')

    def get_headshot(self, player_name: str, player_id: Any = None, team: str = '') -> str:
        if not player_name or player_name in ['Player', 'Probable Pitcher']:
            return 'https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/generic/headshot/67/current.png'

        clean_name = player_name.strip()
        
        # 1. Exact match in verified registry
        if clean_name in self.registry:
            return self.registry[clean_name]['url']

        # 2. Normalized match (without accents, Jr/Sr suffixes)
        norm_name = clean_name.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u').replace('ñ', 'n')
        norm_name = norm_name.replace(' Jr.', '').replace(' Sr.', '').replace(' II', '').replace(' III', '').strip().lower()

        for reg_name, reg_info in self.registry.items():
            reg_norm = reg_name.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u').replace('ñ', 'n')
            reg_norm = reg_norm.replace(' Jr.', '').replace(' Sr.', '').replace(' II', '').replace(' III', '').strip().lower()
            if norm_name == reg_norm:
                return reg_info['url']

        # 3. ID-based routing
        pid_str = str(player_id or '').strip()
        if pid_str.isdigit():
            val = int(pid_str)
            if val < 100000:
                return f'https://a.espncdn.com/i/headshots/mlb/players/full/{val}.png'
            else:
                return f'https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/{val}/headshot/67/current.png'

        return 'https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/generic/headshot/67/current.png'

photo_resolver = PlayerPhotoResolver()
