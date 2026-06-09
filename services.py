"""
Camada de serviço para operações comuns do sistema.
Centraliza o carregamento e processamento de dados para evitar redundância.
"""

import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple
from database import load_data, get_db_connection, get_bot_db_connection


logger = logging.getLogger(__name__)

class DataService:
    """Serviço centralizado para gerenciamento de dados."""
    
    def __init__(self):
        self._cache = {}
        
    def get_core_data(self, force_refresh: bool = False) -> Dict[str, pd.DataFrame]:
        cache_key = "core_data"
        if force_refresh or cache_key not in self._cache:
            import concurrent.futures
            try:
                logger.info("Carregando dados essenciais do sistema em paralelo...")
                db_conn = get_bot_db_connection() or get_db_connection()
                tables = {
                    'alunos': 'Alunos',
                    'acoes': 'Acoes',
                    'tipos_acao': 'Tipos_Acao',
                    'config': 'Config',
                    'users': 'Users',
                    'permissions': 'Permissions'
                }
                data = {}
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(tables)) as executor:
                    # Dispara todas as consultas de forma assíncrona/paralela
                    future_to_key = {
                        executor.submit(load_data, table_name, db_conn): key 
                        for key, table_name in tables.items()
                    }
                    
                    for future in concurrent.futures.as_completed(future_to_key):
                        key = future_to_key[future]
                        try:
                            df = future.result()
                            data[key] = df
                            if df.empty:
                                logger.warning(f"Tabela {tables[key]} está vazia ou falhou")
                        except Exception as exc:
                            logger.error(f"Erro ao carregar {tables[key]} em paralelo: {exc}")
                            data[key] = pd.DataFrame()
                            
                self._cache[cache_key] = data
                logger.info("Dados essenciais carregados com sucesso em paralelo")
            except Exception as e:
                logger.error(f"[ERRO] Falha no carregamento paralelo: {e}")
                return {}
        return self._cache[cache_key]
    
    def get_alunos_data(self, force_refresh: bool = False) -> pd.DataFrame:
        return self.get_core_data(force_refresh).get('alunos', pd.DataFrame())
    
    def get_acoes_data(self, force_refresh: bool = False) -> pd.DataFrame:
        return self.get_core_data(force_refresh).get('acoes', pd.DataFrame())
    
    def get_tipos_acao_data(self, force_refresh: bool = False) -> pd.DataFrame:
        return self.get_core_data(force_refresh).get('tipos_acao', pd.DataFrame())
    
    def get_config_data(self, force_refresh: bool = False) -> pd.DataFrame:
        return self.get_core_data(force_refresh).get('config', pd.DataFrame())
    
    def clear_cache(self):
        self._cache.clear()
        logger.info("Cache de dados limpo")
    
    def get_config_value(self, key: str, default=None, force_refresh: bool = False) -> any:
        config_df = self.get_config_data(force_refresh)
        if config_df.empty or key not in config_df['chave'].values:
            return default
        try:
            return config_df[config_df['chave'] == key]['valor'].iloc[0]
        except (IndexError, KeyError):
            logger.warning(f"Chave de configuração '{key}' não encontrada")
            return default

class ValidationService:
    @staticmethod
    def validate_email(email: str) -> Tuple[bool, str]:
        if not email or '@' not in email or '.' not in email:
            return False, "E-mail inválido"
        return True, ""
    
    @staticmethod
    def validate_password(password: str) -> Tuple[bool, str]:
        if len(password) < 6:
            return False, "Senha deve ter pelo menos 6 caracteres"
        return True, ""

# Instância global dos serviços
data_service = DataService()
validation_service = ValidationService()
