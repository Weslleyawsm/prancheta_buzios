import mysql.connector
from datetime import datetime, time


class DatabaseManager:
    def __init__(self):
        self.config = {
            'host': 'prancheta-db.cgz4mmcgy3ns.us-east-1.rds.amazonaws.com',
            'user': 'admin',
            'password': 'awsm1944',
            'database': 'prancheta_db',
            # 'auth_plugin': 'mysql_native_password'
        }
        self.fiscal_atual = None
        self.data_atual = None
        self.linha_atual = None

    def connect(self):
        return mysql.connector.connect(**self.config)

    def cabecalho_prancheta(self, nome_fiscal, data_atual, linha_atual):
        self.fiscal_atual = nome_fiscal
        self.data_atual = data_atual
        self.linha_atual = linha_atual

        print(f"Cabeçalho definido: {self.fiscal_atual} - {self.data_atual} - {self.linha_atual}")

    def inserir_dados_motorista(self, numero_carro, nome_motorista, horario_saida):
        if not self.fiscal_atual or not self.data_atual or not self.linha_atual:
            print(f"Defina todo o cabeçalho antes de prosseguir!")
            return False
        conexao = self.connect()
        cursor = conexao.cursor()

        sql = """INSERT INTO saida_carros
        (nome_fiscal, data_trabalho, linha, numero_carro, nome_motorista, horario_saida)
        VALUES (%s, %s, %s, %s, %s, %s)"""

        valores = (self.fiscal_atual, self.data_atual, self.linha_atual, numero_carro, nome_motorista, horario_saida)

        cursor.execute(sql, valores)
        conexao.commit()

        cursor.close()
        conexao.close()

        print(f"Salvo: {numero_carro} - {nome_motorista} - {horario_saida}")
        # return True
        return self.listar_registros()

    def listar_registros(self):
        conexao = self.connect()
        cursor = conexao.cursor()

        sql = """SELECT * FROM saida_carros WHERE nome_fiscal = %s AND data_trabalho = %s AND linha = %s"""
        valores = (self.fiscal_atual, self.data_atual, self.linha_atual)

        cursor.execute(sql, valores)
        resultado = cursor.fetchall()

        cursor.close()
        conexao.close()

        print(f"Listando Registro atual!")
        return resultado

    def deletar_registro(self, id_registro):
        conexao = self.connect()
        cursor = conexao.cursor()

        sql = """SELECT * FROM saida_carros WHERE id = (%s)"""
        cursor.execute(sql, (id_registro,))
        registro = cursor.fetchone()
        if not registro:
            print(f"Registro com o ID {id_registro} não encontrado!")
            cursor.close()
            conexao.close()
            return False

        sql = """DELETE FROM saida_carros WHERE id = %s"""
        valores = (id_registro)

        cursor.execute(sql, (valores,))
        conexao.commit()

        cursor.close()
        conexao.close()
        print(f"Registro com id: {id_registro} deletado!")
        return True

        print(f"Registro deletado com sucesso!")

    def listar_todos_registros(self):
        """Lista TODOS os registros sem filtro - COM STATUS DE CONFIRMAÇÃO"""
        conexao = self.connect()
        cursor = conexao.cursor()

        sql = "SELECT * FROM saida_carros ORDER BY id DESC"  # Mais recentes primeiro
        cursor.execute(sql)
        resultado = cursor.fetchall()

        cursor.close()
        conexao.close()

        print(f"Listando TODOS os registros! Total: {len(resultado)}")
        return resultado

    def listar_registros_sessao_atual(self):
        """Lista apenas registros da sessão atual (com cabeçalho definido) - COM STATUS DE CONFIRMAÇÃO"""
        if not self.fiscal_atual or not self.data_atual or not self.linha_atual:
            print("❌ Cabeçalho não definido!")
            return []

        conexao = self.connect()
        cursor = conexao.cursor()

        sql = """SELECT * FROM saida_carros 
                 WHERE nome_fiscal = %s AND data_trabalho = %s AND linha = %s
                 ORDER BY horario_saida ASC"""
        valores = (self.fiscal_atual, self.data_atual, self.linha_atual)

        cursor.execute(sql, valores)
        resultado = cursor.fetchall()

        cursor.close()
        conexao.close()

        print(f"Listando registros da sessão atual! Total: {len(resultado)}")
        return resultado

    # ========== NOVA FUNCIONALIDADE: CONFIRMAR SAÍDA ==========

    def adicionar_coluna_saida_confirmada(self):
        """
        EXECUTE ESTA FUNÇÃO APENAS UMA VEZ para adicionar a nova coluna
        """
        try:
            conexao = self.connect()
            cursor = conexao.cursor()

            sql = """
            ALTER TABLE saida_carros 
            ADD COLUMN saida_confirmada BOOLEAN DEFAULT FALSE
            """

            cursor.execute(sql)
            conexao.commit()

            cursor.close()
            conexao.close()

            print("✅ Coluna 'saida_confirmada' adicionada com sucesso!")
            return True

        except Exception as e:
            print(f"❌ Erro ao adicionar coluna: {str(e)}")
            # Se a coluna já existir, isso é normal
            if "Duplicate column name" in str(e) or "duplicate column name" in str(e).lower():
                print("✅ Coluna já existe, continuando...")
                return True
            return False

    def confirmar_saida_carro(self, id_carro):
        """
        Marca um carro como tendo sua saída confirmada
        """
        try:
            conexao = self.connect()
            cursor = conexao.cursor()

            sql = """
            UPDATE saida_carros 
            SET saida_confirmada = TRUE 
            WHERE id = %s
            """

            cursor.execute(sql, (id_carro,))
            conexao.commit()

            linhas_afetadas = cursor.rowcount
            cursor.close()
            conexao.close()

            if linhas_afetadas > 0:
                print(f"✅ Saída confirmada para carro ID: {id_carro}")
                return True
            else:
                print(f"❌ Carro ID {id_carro} não encontrado")
                return False

        except Exception as e:
            print(f"❌ Erro ao confirmar saída: {str(e)}")
            return False

    def executar_migracao_inicial(self):
        """
        Execute esta função UMA VEZ para preparar o banco de dados
        """
        print("🔧 Executando migração do banco de dados...")

        # Adicionar a nova coluna
        resultado = self.adicionar_coluna_saida_confirmada()

        if resultado:
            print("✅ Migração concluída com sucesso!")
            print("📝 Agora o sistema pode persistir confirmações de saída!")
        else:
            print("❌ Erro na migração!")

        return resultado

    def resetar_todas_confirmacoes(self):
        """
        APENAS PARA TESTES: Reseta todas as confirmações
        """
        try:
            conexao = self.connect()
            cursor = conexao.cursor()

            sql = "UPDATE saida_carros SET saida_confirmada = FALSE"

            cursor.execute(sql)
            conexao.commit()

            cursor.close()
            conexao.close()

            print("🔄 Todas as confirmações foram resetadas")
            return True

        except Exception as e:
            print(f"❌ Erro ao resetar confirmações: {str(e)}")
            return False

    # ========== FUNCIONALIDADES EXISTENTES ATUALIZADAS ==========

    def finalizar_dia(self):
        """
        Finaliza o dia atual, salvando todos os dados e limpando a sessão.
        Retorna resumo do que foi salvo.
        """
        if not self.fiscal_atual or not self.data_atual or not self.linha_atual:
            print("❌ Nenhuma sessão ativa para finalizar!")
            return {
                'status': 'erro',
                'mensagem': 'Nenhuma sessão ativa para finalizar!'
            }

        try:
            # Buscar quantos registros foram feitos hoje
            registros_hoje = self.listar_registros_sessao_atual()
            total_registros = len(registros_hoje)

            # Salvar dados do dia que está sendo finalizado
            dados_finalizados = {
                'fiscal': self.fiscal_atual,
                'data': self.data_atual,
                'linha': self.linha_atual,
                'total_carros': total_registros,
                'registros': registros_hoje
            }

            # Limpar variáveis de sessão
            self.fiscal_atual = None
            self.data_atual = None
            self.linha_atual = None

            print(f"✅ Dia finalizado com sucesso! {total_registros} carros cadastrados.")

            return {
                'status': 'sucesso',
                'mensagem': f'Dia finalizado! {total_registros} carros foram cadastrados.',
                'dados': dados_finalizados
            }

        except Exception as e:
            print(f"❌ Erro ao finalizar dia: {str(e)}")
            return {
                'status': 'erro',
                'mensagem': f'Erro ao finalizar dia: {str(e)}'
            }

    def consultar_por_data(self, data_consulta):
        """
        Consulta todos os registros de uma data específica - COM STATUS DE CONFIRMAÇÃO.

        Args:
            data_consulta (str): Data no formato 'YYYY-MM-DD'

        Returns:
            list: Lista de registros da data especificada
        """
        try:
            conexao = self.connect()
            cursor = conexao.cursor()

            sql = """SELECT * FROM saida_carros 
                     WHERE DATE(data_trabalho) = %s 
                     ORDER BY horario_saida ASC"""

            cursor.execute(sql, (data_consulta,))
            resultado = cursor.fetchall()

            cursor.close()
            conexao.close()

            print(f"📅 Consultando data {data_consulta}: {len(resultado)} registros encontrados")
            return resultado

        except Exception as e:
            print(f"❌ Erro ao consultar por data: {str(e)}")
            return []

    def consultar_por_filtros(self, filtros):
        """
        Consulta registros com múltiplos filtros - COM STATUS DE CONFIRMAÇÃO.

        Args:
            filtros (dict): Dicionário com filtros possíveis:
                - data_inicio: Data de início (YYYY-MM-DD)
                - data_fim: Data de fim (YYYY-MM-DD)
                - fiscal: Nome do fiscal
                - linha: Linha específica
                - numero_carro: Número do carro
                - nome_motorista: Nome do motorista

        Returns:
            list: Lista de registros que atendem aos filtros
        """
        try:
            conexao = self.connect()
            cursor = conexao.cursor()

            # Construir query dinamicamente baseada nos filtros
            sql = "SELECT * FROM saida_carros WHERE 1=1"
            valores = []

            # Filtro por data específica
            if filtros.get('data_especifica'):
                sql += " AND DATE(data_trabalho) = %s"
                valores.append(filtros['data_especifica'])

            # Filtro por período
            if filtros.get('data_inicio'):
                sql += " AND DATE(data_trabalho) >= %s"
                valores.append(filtros['data_inicio'])

            if filtros.get('data_fim'):
                sql += " AND DATE(data_trabalho) <= %s"
                valores.append(filtros['data_fim'])

            # Filtro por fiscal
            if filtros.get('fiscal'):
                sql += " AND nome_fiscal LIKE %s"
                valores.append(f"%{filtros['fiscal']}%")

            # Filtro por linha
            if filtros.get('linha'):
                sql += " AND linha LIKE %s"
                valores.append(f"%{filtros['linha']}%")

            # Filtro por número do carro
            if filtros.get('numero_carro'):
                sql += " AND numero_carro LIKE %s"
                valores.append(f"%{filtros['numero_carro']}%")

            # Filtro por nome do motorista
            if filtros.get('nome_motorista'):
                sql += " AND nome_motorista LIKE %s"
                valores.append(f"%{filtros['nome_motorista']}%")

            # Ordenar por data e horário
            sql += " ORDER BY data_trabalho DESC, horario_saida ASC"

            cursor.execute(sql, valores)
            resultado = cursor.fetchall()

            cursor.close()
            conexao.close()

            print(f"🔍 Consulta com filtros: {len(resultado)} registros encontrados")
            print(f"🔍 Filtros aplicados: {filtros}")

            return resultado

        except Exception as e:
            print(f"❌ Erro ao consultar com filtros: {str(e)}")
            return []

    def obter_estatisticas_periodo(self, data_inicio, data_fim):
        """
        Retorna estatísticas de um período específico.

        Args:
            data_inicio (str): Data de início (YYYY-MM-DD)
            data_fim (str): Data de fim (YYYY-MM-DD)

        Returns:
            dict: Estatísticas do período
        """
        try:
            conexao = self.connect()
            cursor = conexao.cursor()

            # Total de carros no período
            sql_total = """SELECT COUNT(*) FROM saida_carros 
                          WHERE DATE(data_trabalho) BETWEEN %s AND %s"""
            cursor.execute(sql_total, (data_inicio, data_fim))
            total_carros = cursor.fetchone()[0]

            # Carros por fiscal
            sql_fiscal = """SELECT nome_fiscal, COUNT(*) as total 
                           FROM saida_carros 
                           WHERE DATE(data_trabalho) BETWEEN %s AND %s 
                           GROUP BY nome_fiscal 
                           ORDER BY total DESC"""
            cursor.execute(sql_fiscal, (data_inicio, data_fim))
            por_fiscal = cursor.fetchall()

            # Carros por linha
            sql_linha = """SELECT linha, COUNT(*) as total 
                          FROM saida_carros 
                          WHERE DATE(data_trabalho) BETWEEN %s AND %s 
                          GROUP BY linha 
                          ORDER BY total DESC"""
            cursor.execute(sql_linha, (data_inicio, data_fim))
            por_linha = cursor.fetchall()

            # Carros por dia
            sql_dia = """SELECT DATE(data_trabalho) as data, COUNT(*) as total 
                        FROM saida_carros 
                        WHERE DATE(data_trabalho) BETWEEN %s AND %s 
                        GROUP BY DATE(data_trabalho) 
                        ORDER BY data DESC"""
            cursor.execute(sql_dia, (data_inicio, data_fim))
            por_dia = cursor.fetchall()

            cursor.close()
            conexao.close()

            estatisticas = {
                'periodo': {'inicio': data_inicio, 'fim': data_fim},
                'total_carros': total_carros,
                'por_fiscal': [{'fiscal': row[0], 'total': row[1]} for row in por_fiscal],
                'por_linha': [{'linha': row[0], 'total': row[1]} for row in por_linha],
                'por_dia': [{'data': str(row[0]), 'total': row[1]} for row in por_dia]
            }

            print(f"📊 Estatísticas calculadas para {data_inicio} a {data_fim}")
            return estatisticas

        except Exception as e:
            print(f"❌ Erro ao calcular estatísticas: {str(e)}")
            return {}

    def obter_sessao_atual(self):
        """
        Retorna informações da sessão atual.

        Returns:
            dict: Dados da sessão atual ou None se não houver sessão ativa
        """
        if not self.fiscal_atual or not self.data_atual or not self.linha_atual:
            return None

        try:
            registros = self.listar_registros_sessao_atual()
            return {
                'fiscal': self.fiscal_atual,
                'data': self.data_atual,
                'linha': self.linha_atual,
                'total_carros': len(registros),
                'ativa': True
            }
        except Exception as e:
            print(f"❌ Erro ao obter sessão atual: {str(e)}")
            return None

    def editar_registros(self, id_registro, nome_fiscal, data_trabalho, linha, numero_carro, nome_motorista,
                         horario_saida):
        try:
            conexao = self.connect()
            cursor = conexao.cursor()

            # Verificar se o registro existe antes de editar
            sql_verificar = "SELECT * FROM saida_carros WHERE id = %s"
            cursor.execute(sql_verificar, (id_registro,))
            registro = cursor.fetchone()

            if not registro:
                print(f"❌ Registro com ID {id_registro} não encontrado!")
                cursor.close()
                conexao.close()
                return False

            # Query UPDATE corrigida - note que todas as colunas têm = %s
            sql = """UPDATE saida_carros 
                     SET nome_fiscal = %s, 
                         data_trabalho = %s, 
                         linha = %s, 
                         numero_carro = %s, 
                         nome_motorista = %s, 
                         horario_saida = %s 
                     WHERE id = %s"""

            # Valores na ordem correta (mesma ordem da query)
            valores = (nome_fiscal, data_trabalho, linha, numero_carro, nome_motorista, horario_saida, id_registro)

            cursor.execute(sql, valores)
            conexao.commit()

            cursor.close()
            conexao.close()

            print(f"✅ Registro {id_registro} editado com sucesso!")
            return True

        except Exception as e:
            print(f"❌ Erro ao editar registro: {str(e)}")
            return False


if __name__ == '__main__':
    db = DatabaseManager()
    try:
        conexao = db.connect()
        print("Conexão criada com sucesso!")
        conexao.close()

        # DESCOMENTE A LINHA ABAIXO PARA EXECUTAR A MIGRAÇÃO UMA VEZ:
        # db.executar_migracao_inicial()

    except Exception as e:
        print(f"Erro na conexão: {e}")
