import pytest
from unittest.mock import Mock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSecurity:
    """Testes de segurança"""
    
    def test_role_permissions(self):
        from security import Role, PERMISSIONS, has_permission
        
        assert Role.ADMIN.value == "admin"
        assert "dashboard.view" in PERMISSIONS[Role.ADMIN]
        assert "dashboard.view" in PERMISSIONS[Role.OPERADOR]
    
    def test_can_access(self):
        from security import can_access, Role
        
        with patch('security.get_user_role') as mock_role:
            mock_role.return_value = Role.OPERADOR
            
            assert can_access('dashboard', 'view') == True
            assert can_access('workflow', 'delete') == False
    
    def test_audit_log(self):
        from security import log_audit, get_audit_log
        
        class MockStorage:
            def __init__(self):
                self.user = {'audit_log': []}
        
        mock_storage = MockStorage()
        with patch('security.app.storage', mock_storage):
            log_audit('test_action', {'detail': 'test'})
            log = get_audit_log()
            
            assert len(log) > 0
            assert log[-1]['action'] == 'test_action'


class TestAIHelper:
    """Testes do módulo de IA"""
    
    def test_summarize_text_no_api(self):
        from ai_helper import summarize_text
        
        with patch('ai_helper.GOOGLE_API_KEY', ''):
            result = summarize_text("texto longo...")
            assert "API Key não configurada" in result
    
    def test_translate_text_no_api(self):
        from ai_helper import translate_text
        
        with patch('ai_helper.GOOGLE_API_KEY', ''):
            result = translate_text("hello", "pt")
            assert "API Key não configurada" in result
    
    def test_chat_no_api(self):
        from ai_helper import chat_with_ai
        
        with patch('ai_helper.GOOGLE_API_KEY', ''):
            result = chat_with_ai("oi")
            assert "API Key não configurada" in result


class TestDatabase:
    """Testes do banco de dados"""
    
    def test_get_db_connection_none(self):
        import database
        old_db = database.db
        database.db = None
        try:
            with patch('database.SUPABASE_URL', ''), patch('database.SUPABASE_KEY', ''):
                result = database.get_db_connection()
                assert result is None
        finally:
            database.db = old_db
    
    def test_authenticate_no_db(self):
        from database import authenticate_user
        
        with patch('database.get_db_connection') as mock_db:
            mock_db.return_value = None
            
            result = authenticate_user("user", "pass")
            assert result is None
            
    def test_carregar_presenca_offline(self):
        from database import carregar_presenca_hoje
        
        with patch('database.get_db_connection') as mock_db:
            mock_db.return_value = None
            
            df = carregar_presenca_hoje()
            assert not df.empty
            assert 'nome_guerra' in df.columns
            
    def test_carregar_enfermaria_offline(self):
        from database import carregar_enfermaria_hoje
        
        with patch('database.get_db_connection') as mock_db:
            mock_db.return_value = None
            
            df = carregar_enfermaria_hoje()
            assert not df.empty
            assert 'status' in df.columns

    def test_salvar_presenca_offline(self):
        from database import salvar_presenca_supabase
        with patch('database.get_db_connection') as mock_db:
            mock_db.return_value = None
            result = salvar_presenca_supabase(101, 'Silva', 'Alfa', True)
            assert result is True

    def test_salvar_enfermaria_offline(self):
        from database import salvar_enfermaria_supabase
        with patch('database.get_db_connection') as mock_db:
            mock_db.return_value = None
            result = salvar_enfermaria_supabase(201, 'Oliveira', 'Bravo', 'baixado', 'Gripe')
            assert result is True

    def test_salvar_oficial_servico_offline(self):
        from database import salvar_oficial_servico
        with patch('database.get_db_connection') as mock_db:
            mock_db.return_value = None
            result = salvar_oficial_servico('Cap. Calaça', 'Oficial de Dia', 'Sgt. Silva')
            assert result is True

    def test_carregar_oficiais_offline(self):
        from database import carregar_oficiais_hoje
        with patch('database.get_db_connection') as mock_db:
            mock_db.return_value = None
            df = carregar_oficiais_hoje()
            assert not df.empty
            assert 'nome' in df.columns

    def test_carregar_fila_offline(self):
        from database import carregar_fila_atendimento
        with patch('database.get_db_connection') as mock_db:
            mock_db.return_value = None
            df = carregar_fila_atendimento()
            assert not df.empty
            assert 'prioridade' in df.columns

    def test_salvar_pernoites_offline(self):
        from database import salvar_pernoites_supabase
        with patch('database.get_db_connection') as mock_db:
            mock_db.return_value = None
            res = salvar_pernoites_supabase([{'aluno_id': 1, 'data': '2026-05-29', 'presente': True}])
            assert res is True

    def test_carregar_pernoites_offline(self):
        from database import load_data
        with patch('database.get_db_connection') as mock_db:
            mock_db.return_value = None
            df = load_data('pernoite')
            assert not df.empty
            assert 'presente' in df.columns

    def test_transporte_excel_template(self):
        from alunos_transporte import create_excel_template
        template_bytes = create_excel_template()
        assert len(template_bytes) > 0



class TestTelegramBot:
    """Testes do Telegram Bot"""
    
    def test_bot_no_token(self):
        import sys
        if 'telegram_bot' in sys.modules:
            del sys.modules['telegram_bot']
            
        with patch.dict(os.environ, {'TELEGRAM_TOKEN': ''}):
            import telegram_bot
            assert not telegram_bot.bot



class TestSiscomcaDashboard:
    """Testes do dashboard e programacao"""
    
    def test_dashboard_import(self):
        import siscomca_dashboard
        assert hasattr(siscomca_dashboard, 'render_page')

    def test_programacao_import(self):
        import programacao
        assert hasattr(programacao, 'render_page')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

