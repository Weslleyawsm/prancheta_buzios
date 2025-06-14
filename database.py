import mysql.connector
from datetime import datetime, time, timedelta


class DatabaseManager:
    def __init__(self):
        self.config = {
            'host': 'prancheta-db.cgz4mmcgy3ns.us-east-1.rds.amazonaws.com',
            'user': 'admin',
            'password': 'awsm1944',
            'database': 'prancheta_db',
        }
        self.fiscal_atual = None
        self.data_atual = None
        self.linha_atual = None  # Sempre será None agora
        self.intervalo_atual = 8  # Intervalo padrão em minutos (MANTIDO para compatibilidade)

        # 🆕 NOVO: Intervalos específicos por linha
        self.intervalos_por_linha = {
            'Centro x Vila Verde': 8,  # Padrão 8 minutos
            'Centro x Rasa': 8  # Padrão 8 minutos
        }

    def connect(self):
        return mysql.connector.connect(**self.config)

    def cabecalho_prancheta(self, nome_fiscal, data_atual):
        """Cabeçalho simplificado - apenas fiscal e data"""
        self.fiscal_atual = nome_fiscal
        self.data_atual = data_atual
        self.linha_atual = None  # Linha será definida por carro

        print(f"Cabeçalho definido: {self.fiscal_atual} - {self.data_atual}")

    # 🆕 NOVAS FUNÇÕES: Gestão de Intervalos por Linha

    def obter_intervalo_linha(self, nome_linha):
        """Retorna o intervalo específico de uma linha"""
        return self.intervalos_por_linha.get(nome_linha, 8)  # Default 8 min

    def definir_intervalo_linha(self, nome_linha, novo_intervalo):
        """Define intervalo específico para uma linha"""
        try:
            if not isinstance(novo_intervalo, int) or novo_intervalo < 1 or novo_intervalo > 60:
                return {'status': 'erro', 'mensagem': 'Intervalo deve ser entre 1 e 60 minutos'}

            if nome_linha not in self.intervalos_por_linha:
                return {'status': 'erro', 'mensagem': f'Linha "{nome_linha}" não reconhecida'}

            print(f"🔧 Definindo intervalo para {nome_linha}: {novo_intervalo} minutos")

            # Salvar intervalo antigo para log
            intervalo_antigo = self.intervalos_por_linha[nome_linha]
            self.intervalos_por_linha[nome_linha] = novo_intervalo

            # Recalcular horários dos carros pendentes DESTA linha específica
            carros_atualizados = self.recalcular_horarios_linha_especifica(nome_linha)

            return {
                'status': 'sucesso',
                'linha': nome_linha,
                'intervalo_antigo': intervalo_antigo,
                'intervalo_novo': novo_intervalo,
                'carros_atualizados': carros_atualizados,
                'mensagem': f'Intervalo da linha "{nome_linha}" alterado para {novo_intervalo} minutos. {carros_atualizados} carros atualizados.'
            }

        except Exception as e:
            print(f"❌ Erro ao definir intervalo da linha: {str(e)}")
            return {'status': 'erro', 'mensagem': f'Erro: {str(e)}'}

    def calcular_proximo_horario_linha(self, nome_linha):
        """Calcula próximo horário baseado no ÚLTIMO carro DA LINHA ESPECÍFICA com lógica inteligente"""
        try:
            conexao = self.connect()
            cursor = conexao.cursor()

            print(f"🔍 Calculando próximo horário para linha: {nome_linha}")
            print(f"🔍 Fiscal: {self.fiscal_atual}, Data: {self.data_atual}")

            # 🎯 PASSO 1: Verificar se há carros AGUARDANDO na linha
            sql_aguardando = """SELECT horario_saida FROM saida_carros 
                               WHERE nome_fiscal = %s AND data_trabalho = %s AND linha = %s
                               AND saida_confirmada = FALSE
                               ORDER BY horario_saida DESC 
                               LIMIT 1"""

            valores = (self.fiscal_atual, self.data_atual, nome_linha)
            cursor.execute(sql_aguardando, valores)
            ultimo_aguardando = cursor.fetchone()

            print(f"🔍 Último carro AGUARDANDO da linha {nome_linha}: {ultimo_aguardando}")

            # Se há carro aguardando, usar ele + intervalo
            if ultimo_aguardando and ultimo_aguardando[0]:
                ultimo_horario = ultimo_aguardando[0]

                # Converter timedelta para time se necessário
                if isinstance(ultimo_horario, timedelta):
                    total_seconds = int(ultimo_horario.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    ultimo_horario = time(hours, minutes, 0)
                    print(f"🔧 Convertido timedelta para time: {ultimo_horario}")

                if isinstance(ultimo_horario, time):
                    ultimo_datetime = datetime.combine(datetime.now().date(), ultimo_horario)
                    intervalo_linha = self.obter_intervalo_linha(nome_linha)
                    proximo_datetime = ultimo_datetime + timedelta(minutes=intervalo_linha)
                    proximo_horario = proximo_datetime.time().replace(second=0, microsecond=0)
                    print(
                        f"⏰ {nome_linha}: Último aguardando ({ultimo_horario}) + {intervalo_linha}min = {proximo_horario}")
                    cursor.close()
                    conexao.close()
                    return proximo_horario

            # 🎯 PASSO 2: Se NÃO há carros aguardando, verificar último CONFIRMADO
            sql_confirmado = """SELECT horario_saida FROM saida_carros 
                               WHERE nome_fiscal = %s AND data_trabalho = %s AND linha = %s
                               AND saida_confirmada = TRUE
                               ORDER BY horario_saida DESC 
                               LIMIT 1"""

            cursor.execute(sql_confirmado, valores)
            ultimo_confirmado = cursor.fetchone()

            print(f"🔍 Último carro CONFIRMADO da linha {nome_linha}: {ultimo_confirmado}")

            agora = datetime.now()
            intervalo_linha = self.obter_intervalo_linha(nome_linha)
            print(f"🔍 Intervalo da linha {nome_linha}: {intervalo_linha} minutos")
            print(f"🔍 Horário atual: {agora.strftime('%H:%M:%S')}")

            if ultimo_confirmado and ultimo_confirmado[0]:
                ultimo_horario = ultimo_confirmado[0]

                # Converter timedelta para time se necessário
                if isinstance(ultimo_horario, timedelta):
                    total_seconds = int(ultimo_horario.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    ultimo_horario = time(hours, minutes, 0)
                    print(f"🔧 Convertido timedelta para time: {ultimo_horario}")

                if isinstance(ultimo_horario, time):
                    ultimo_datetime = datetime.combine(datetime.now().date(), ultimo_horario)
                    horario_esperado_datetime = ultimo_datetime + timedelta(minutes=intervalo_linha)
                    horario_esperado = horario_esperado_datetime.time()

                    print(f"🔍 Último confirmado: {ultimo_horario}")
                    print(f"🔍 Horário esperado seria: {horario_esperado}")

                    # 🎯 REGRA INTELIGENTE: Se passou do tempo, usar agora + intervalo
                    if agora.time() > horario_esperado:
                        print(f"⚡ CARRO ATRASADO! Passou do horário esperado ({horario_esperado})")
                        print(f"⚡ Usando horário atual + {intervalo_linha} minutos")
                        proximo_datetime = agora + timedelta(minutes=intervalo_linha)
                        proximo_horario = proximo_datetime.time().replace(second=0, microsecond=0)
                        print(f"⏰ Novo horário calculado: {proximo_horario}")
                        cursor.close()
                        conexao.close()
                        return proximo_horario
                    else:
                        print(f"✅ Dentro do prazo, usando horário esperado: {horario_esperado}")
                        cursor.close()
                        conexao.close()
                        return horario_esperado.replace(second=0, microsecond=0)

            # 🎯 PASSO 3: Primeiro carro da linha - usar horário atual + 10 minutos
            proximo_datetime = agora + timedelta(minutes=10)
            proximo_horario = proximo_datetime.time().replace(second=0, microsecond=0)
            print(f"⏰ PRIMEIRO carro da linha {nome_linha}: {proximo_horario} (agora + 10 minutos)")

            cursor.close()
            conexao.close()
            return proximo_horario

        except Exception as e:
            print(f"❌ Erro ao calcular próximo horário da linha: {e}")
            agora = datetime.now()
            return (agora + timedelta(minutes=10)).time().replace(second=0, microsecond=0)

    def recalcular_horarios_linha_especifica(self, nome_linha):
        """Recalcula horários apenas dos carros pendentes DE UMA LINHA ESPECÍFICA usando LÓGICA INTELIGENTE"""
        try:
            if not self.fiscal_atual or not self.data_atual:
                print("❌ Cabeçalho não definido, não é possível recalcular")
                return 0

            conexao = self.connect()
            cursor = conexao.cursor()

            # Buscar carros PENDENTES DA LINHA ESPECÍFICA
            sql_pendentes = """SELECT id, numero_carro, horario_saida FROM saida_carros 
                              WHERE nome_fiscal = %s AND data_trabalho = %s 
                              AND linha = %s AND saida_confirmada = FALSE
                              ORDER BY horario_saida ASC"""

            valores = (self.fiscal_atual, self.data_atual, nome_linha)
            cursor.execute(sql_pendentes, valores)
            carros_pendentes = cursor.fetchall()

            print(f"🔍 Carros PENDENTES da linha {nome_linha}: {len(carros_pendentes)}")

            if not carros_pendentes:
                print(f"✅ Nenhum carro pendente da linha {nome_linha} para recalcular")
                cursor.close()
                conexao.close()
                return 0

            # 🆕 LÓGICA INTELIGENTE: Usar a mesma lógica do calcular_proximo_horario_linha
            agora = datetime.now()
            intervalo_linha = self.obter_intervalo_linha(nome_linha)

            # Verificar último carro CONFIRMADO da linha
            sql_confirmado = """SELECT horario_saida FROM saida_carros 
                               WHERE nome_fiscal = %s AND data_trabalho = %s AND linha = %s
                               AND saida_confirmada = TRUE
                               ORDER BY horario_saida DESC 
                               LIMIT 1"""

            cursor.execute(sql_confirmado, valores)
            ultimo_confirmado = cursor.fetchone()

            print(f"🔍 Último carro CONFIRMADO da linha {nome_linha}: {ultimo_confirmado}")
            print(f"🔍 Horário atual: {agora.strftime('%H:%M:%S')}")
            print(f"🔍 Intervalo da linha {nome_linha}: {intervalo_linha} minutos")

            # Determinar horário base INTELIGENTE
            if ultimo_confirmado and ultimo_confirmado[0]:
                ultimo_horario = ultimo_confirmado[0]

                # Converter timedelta para time se necessário
                if isinstance(ultimo_horario, timedelta):
                    total_seconds = int(ultimo_horario.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    ultimo_horario = time(hours, minutes, 0)

                if isinstance(ultimo_horario, time):
                    ultimo_datetime = datetime.combine(datetime.now().date(), ultimo_horario)
                    horario_esperado_datetime = ultimo_datetime + timedelta(minutes=intervalo_linha)
                    horario_esperado = horario_esperado_datetime.time()

                    print(f"🔍 Último confirmado: {ultimo_horario}")
                    print(f"🔍 Horário esperado seria: {horario_esperado}")

                    # 🎯 REGRA INTELIGENTE: Se passou do tempo, usar agora + intervalo
                    if agora.time() > horario_esperado:
                        print(f"⚡ CARRO ATRASADO! Passou do horário esperado ({horario_esperado})")
                        print(f"⚡ Usando horário atual + {intervalo_linha} minutos para BASE")
                        horario_base_datetime = agora + timedelta(minutes=intervalo_linha)
                    else:
                        print(f"✅ Dentro do prazo, usando horário esperado como BASE: {horario_esperado}")
                        horario_base_datetime = horario_esperado_datetime
            else:
                # Primeiro da linha - usar horário atual + 10 minutos
                print(f"⏰ PRIMEIRO carro da linha {nome_linha} - usando agora + 10 min como BASE")
                horario_base_datetime = agora + timedelta(minutes=10)

            horario_base_datetime = horario_base_datetime.replace(second=0, microsecond=0)
            print(f"⏰ BASE FINAL para recálculo da linha {nome_linha}: {horario_base_datetime.strftime('%H:%M:%S')}")

            carros_atualizados = 0

            # Recalcular carros pendentes baseado na BASE INTELIGENTE
            for i, (id_carro, numero_carro, horario_antigo) in enumerate(carros_pendentes):
                # Calcular novo horário
                novo_horario_datetime = horario_base_datetime + timedelta(minutes=i * intervalo_linha)
                novo_horario_datetime = novo_horario_datetime.replace(second=0, microsecond=0)
                novo_horario_time = novo_horario_datetime.time()

                print(
                    f"🔧 Linha {nome_linha} - Atualizando ID {id_carro} (Carro {numero_carro}): {horario_antigo} → {novo_horario_time}")

                # Atualizar horário
                sql_update = """UPDATE saida_carros 
                               SET horario_saida = %s 
                               WHERE id = %s"""

                cursor.execute(sql_update, (novo_horario_time, id_carro))

                if cursor.rowcount == 1:
                    carros_atualizados += 1
                    print(f"✅ ID {id_carro} atualizado com sucesso")

            # Commit das alterações
            conexao.commit()
            print(f"💾 Linha {nome_linha}: {carros_atualizados} carros atualizados com LÓGICA INTELIGENTE")

            cursor.close()
            conexao.close()

            return carros_atualizados

        except Exception as e:
            print(f"❌ ERRO ao recalcular horários da linha {nome_linha}: {str(e)}")
            try:
                conexao.rollback()
                cursor.close()
                conexao.close()
            except:
                pass
            return 0

    # 🔄 FUNÇÃO MODIFICADA: inserir_dados_motorista agora usa horário por linha
    def inserir_dados_motorista(self, numero_carro, nome_motorista, linha_carro, horario_saida=None):
        """
        Insere carro com horário automático POR LINHA se não fornecido
        """
        if not self.fiscal_atual or not self.data_atual:
            print(f"❌ Defina o cabeçalho (fiscal e data) antes de prosseguir!")
            return False

        try:
            # Se horário não fornecido, calcular por linha específica
            if horario_saida is None:
                horario_saida = self.calcular_proximo_horario_linha(linha_carro)
                print(f"🕐 Horário calculado para linha {linha_carro}: {horario_saida}")

            # Garantir que horário sempre tenha segundos = 00
            if isinstance(horario_saida, str):
                horario_obj = datetime.strptime(horario_saida, '%H:%M').time()
            else:
                horario_obj = horario_saida

            horario_final = horario_obj.replace(second=0, microsecond=0)
            print(f"🕐 Horário final: {horario_final} (segundos zerados)")

            conexao = self.connect()
            cursor = conexao.cursor()

            # Inserir carro (saida_confirmada = FALSE por padrão)
            sql = """INSERT INTO saida_carros
            (nome_fiscal, data_trabalho, linha, numero_carro, nome_motorista, horario_saida, saida_confirmada)
            VALUES (%s, %s, %s, %s, %s, %s, FALSE)"""

            valores = (self.fiscal_atual, self.data_atual, linha_carro, numero_carro, nome_motorista, horario_final)

            cursor.execute(sql, valores)
            conexao.commit()

            cursor.close()
            conexao.close()

            print(f"✅ Salvo: {numero_carro} - {nome_motorista} - {linha_carro} - {horario_final} (AGUARDANDO)")
            return True

        except Exception as e:
            print(f"❌ Erro ao inserir dados: {str(e)}")
            return False

    # 🆕 NOVA FUNÇÃO: Listar carros separados por linha
    def listar_carros_por_linha(self):
        """Lista carros da sessão atual SEPARADOS por linha"""
        if not self.fiscal_atual or not self.data_atual:
            print("❌ Cabeçalho não definido!")
            return {}

        try:
            conexao = self.connect()
            cursor = conexao.cursor()

            sql = """SELECT * FROM saida_carros 
                     WHERE nome_fiscal = %s AND data_trabalho = %s
                     ORDER BY linha ASC, horario_saida ASC"""
            valores = (self.fiscal_atual, self.data_atual)

            cursor.execute(sql, valores)
            todos_registros = cursor.fetchall()

            cursor.close()
            conexao.close()

            # Separar por linha
            carros_por_linha = {}

            for registro in todos_registros:
                linha = registro[3]  # linha está na posição 3

                if linha not in carros_por_linha:
                    carros_por_linha[linha] = []

                carros_por_linha[linha].append(registro)

            print(f"📊 Carros separados por linha:")
            for linha, carros in carros_por_linha.items():
                print(f"  {linha}: {len(carros)} carros")

            return carros_por_linha

        except Exception as e:
            print(f"❌ Erro ao listar carros por linha: {str(e)}")
            return {}

    # ========== MANTER TODAS AS FUNÇÕES ORIGINAIS INTACTAS ==========

    def calcular_proximo_horario(self):
        """
        FUNÇÃO ORIGINAL MANTIDA: Calcula próximo horário baseado no ÚLTIMO carro (independente de confirmação)
        """
        try:
            conexao = self.connect()
            cursor = conexao.cursor()

            print(f"🔍 Calculando próximo horário...")
            print(f"🔍 Fiscal: {self.fiscal_atual}, Data: {self.data_atual}")

            # CORREÇÃO CRÍTICA: Buscar ÚLTIMO carro da sessão (confirmado ou não)
            sql = """SELECT horario_saida FROM saida_carros 
                     WHERE nome_fiscal = %s AND data_trabalho = %s 
                     ORDER BY horario_saida DESC 
                     LIMIT 1"""

            valores = (self.fiscal_atual, self.data_atual)
            cursor.execute(sql, valores)
            ultimo_carro = cursor.fetchone()

            # DEBUG: Ver todos os carros para entender
            sql_debug = """SELECT numero_carro, horario_saida FROM saida_carros 
                          WHERE nome_fiscal = %s AND data_trabalho = %s 
                          ORDER BY horario_saida DESC"""
            cursor.execute(sql_debug, valores)
            todos_carros = cursor.fetchall()

            print(f"🔍 Carros na sessão:")
            for carro in todos_carros:
                print(f"    Carro {carro[0]} - {carro[1]}")

            cursor.close()
            conexao.close()

            if ultimo_carro and ultimo_carro[0]:
                # Há carros - adicionar intervalo ao último
                ultimo_horario = ultimo_carro[0]

                # Converter timedelta para time se necessário
                if isinstance(ultimo_horario, timedelta):
                    # Converter timedelta para time
                    total_seconds = int(ultimo_horario.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    ultimo_horario = time(hours, minutes, 0)
                    print(f"🔧 Convertido timedelta para time: {ultimo_horario}")

                if isinstance(ultimo_horario, time):
                    ultimo_datetime = datetime.combine(datetime.now().date(), ultimo_horario)
                    proximo_datetime = ultimo_datetime + timedelta(minutes=self.intervalo_atual)
                    proximo_horario = proximo_datetime.time().replace(second=0, microsecond=0)
                    print(f"⏰ CORRETO: Último ({ultimo_horario}) + {self.intervalo_atual}min = {proximo_horario}")
                    return proximo_horario
                else:
                    print(f"❌ Tipo inesperado de horário: {type(ultimo_horario)} - {ultimo_horario}")

            # Primeiro carro do dia - usar horário atual + 10 minutos
            agora = datetime.now()
            proximo_datetime = agora + timedelta(minutes=10)
            proximo_horario = proximo_datetime.time().replace(second=0, microsecond=0)
            print(f"⏰ PRIMEIRO carro do dia: {proximo_horario} (agora + 10 minutos)")
            return proximo_horario

        except Exception as e:
            print(f"❌ Erro ao calcular próximo horário: {e}")
            agora = datetime.now()
            return (agora + timedelta(minutes=10)).time().replace(second=0, microsecond=0)

    def listar_registros(self):
        """Lista registros da sessão atual (compatibilidade)"""
        return self.listar_registros_sessao_atual()

    def listar_registros_sessao_atual(self):
        """Lista apenas registros da sessão atual (com cabeçalho definido) - COM STATUS DE CONFIRMAÇÃO"""
        if not self.fiscal_atual or not self.data_atual:
            print("❌ Cabeçalho não definido!")
            return []

        try:
            conexao = self.connect()
            cursor = conexao.cursor()

            sql = """SELECT * FROM saida_carros 
                     WHERE nome_fiscal = %s AND data_trabalho = %s
                     ORDER BY horario_saida ASC"""
            valores = (self.fiscal_atual, self.data_atual)

            cursor.execute(sql, valores)
            resultado = cursor.fetchall()

            cursor.close()
            conexao.close()

            print(f"Listando registros da sessão atual! Total: {len(resultado)}")
            return resultado

        except Exception as e:
            print(f"❌ Erro ao listar registros da sessão: {str(e)}")
            return []

    def listar_todos_registros(self):
        """Lista TODOS os registros sem filtro - COM STATUS DE CONFIRMAÇÃO"""
        conexao = self.connect()
        cursor = conexao.cursor()

        sql = "SELECT * FROM saida_carros ORDER BY id DESC"
        cursor.execute(sql)
        resultado = cursor.fetchall()

        cursor.close()
        conexao.close()

        print(f"Listando TODOS os registros! Total: {len(resultado)}")
        return resultado

    def deletar_registro(self, id_registro):
        """Remove um registro do banco de dados"""
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
        cursor.execute(sql, (id_registro,))
        conexao.commit()

        cursor.close()
        conexao.close()
        print(f"Registro com id: {id_registro} deletado!")
        return True

    # ========== FUNCIONALIDADE: CONFIRMAR SAÍDA AUTOMÁTICA ==========

    def adicionar_coluna_saida_confirmada(self):
        """EXECUTE ESTA FUNÇÃO APENAS UMA VEZ para adicionar a nova coluna"""
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
            if "Duplicate column name" in str(e) or "duplicate column name" in str(e).lower():
                print("✅ Coluna já existe, continuando...")
                return True
            return False

    def confirmar_saida_carro(self, id_carro):
        """Marca um carro como tendo sua saída confirmada AUTOMATICAMENTE"""
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
                print(f"✅ Saída confirmada AUTOMATICAMENTE para carro ID: {id_carro}")
                return True
            else:
                print(f"❌ Carro ID {id_carro} não encontrado")
                return False

        except Exception as e:
            print(f"❌ Erro ao confirmar saída: {str(e)}")
            return False

    # ========== FUNCIONALIDADE ORIGINAL: CONTROLE DE INTERVALO ==========

    def definir_intervalo(self, novo_intervalo):
        """Define novo intervalo entre carros e recalcula horários dos carros pendentes"""
        try:
            if not isinstance(novo_intervalo, int) or novo_intervalo < 1 or novo_intervalo > 60:
                print("❌ Intervalo deve ser um número entre 1 e 60 minutos")
                return {'status': 'erro', 'mensagem': 'Intervalo deve ser entre 1 e 60 minutos'}

            print(f"🔧 Definindo novo intervalo: {novo_intervalo} minutos")
            self.intervalo_atual = novo_intervalo

            # Recalcular horários dos carros pendentes
            carros_atualizados = self.recalcular_horarios_carros_pendentes()

            return {
                'status': 'sucesso',
                'intervalo': novo_intervalo,
                'carros_atualizados': carros_atualizados,
                'mensagem': f'Intervalo alterado para {novo_intervalo} minutos. {carros_atualizados} carros atualizados.'
            }

        except Exception as e:
            print(f"❌ Erro ao definir intervalo: {str(e)}")
            return {'status': 'erro', 'mensagem': f'Erro ao definir intervalo: {str(e)}'}

    def recalcular_horarios_carros_pendentes(self):
        """
        FUNÇÃO ORIGINAL CORRIGIDA: Recalcula horários SEM DUPLICAR registros usando LÓGICA INTELIGENTE
        """
        try:
            if not self.fiscal_atual or not self.data_atual:
                print("❌ Cabeçalho não definido, não é possível recalcular")
                return 0

            conexao = self.connect()
            cursor = conexao.cursor()

            # Buscar apenas carros PENDENTES para recalcular
            sql_pendentes = """SELECT id, numero_carro, horario_saida FROM saida_carros 
                              WHERE nome_fiscal = %s AND data_trabalho = %s 
                              AND saida_confirmada = FALSE
                              ORDER BY id ASC"""

            cursor.execute(sql_pendentes, (self.fiscal_atual, self.data_atual))
            carros_pendentes = cursor.fetchall()

            print(f"🔍 Carros PENDENTES para recalcular (TODAS AS LINHAS): {len(carros_pendentes)}")

            if not carros_pendentes:
                print("✅ Nenhum carro pendente para recalcular")
                cursor.close()
                conexao.close()
                return 0

            # 🆕 LÓGICA INTELIGENTE: Usar horário atual como base (não carros antigos)
            agora = datetime.now()
            horario_base = agora + timedelta(minutes=10)  # Base: agora + 10 minutos
            horario_base = horario_base.replace(second=0, microsecond=0)

            print(f"⏰ BASE INTELIGENTE para recálculo: {horario_base.strftime('%H:%M:%S')} (agora + 10 min)")
            print(f"⏰ INTERVALO GERAL: {self.intervalo_atual} minutos")

            carros_atualizados = 0

            for i, (id_carro, numero_carro, horario_antigo) in enumerate(carros_pendentes):
                # Calcular novo horário baseado na BASE INTELIGENTE
                novo_horario_datetime = horario_base + timedelta(minutes=i * self.intervalo_atual)
                novo_horario_datetime = novo_horario_datetime.replace(second=0, microsecond=0)
                novo_horario_time = novo_horario_datetime.time()

                print(f"🔧 Atualizando ID {id_carro} (Carro {numero_carro}): {horario_antigo} → {novo_horario_time}")

                # ATUALIZAR (não inserir novo registro)
                sql_update = """UPDATE saida_carros 
                               SET horario_saida = %s 
                               WHERE id = %s"""

                cursor.execute(sql_update, (novo_horario_time, id_carro))

                # Verificar se a atualização funcionou
                if cursor.rowcount == 1:
                    carros_atualizados += 1
                    print(f"✅ ID {id_carro} atualizado com sucesso")
                else:
                    print(f"❌ Falha ao atualizar ID {id_carro} - Linhas afetadas: {cursor.rowcount}")

            # COMMIT apenas uma vez no final
            conexao.commit()
            print(f"💾 Transação commitada - {carros_atualizados} carros atualizados com LÓGICA INTELIGENTE")

            cursor.close()
            conexao.close()

            return carros_atualizados

        except Exception as e:
            print(f"❌ ERRO CRÍTICO ao recalcular horários: {str(e)}")
            # Em caso de erro, fazer rollback
            try:
                conexao.rollback()
                cursor.close()
                conexao.close()
            except:
                pass
            return 0

    # ========== SESSÃO E INFORMAÇÕES ==========

    def obter_sessao_atual(self):
        """Retorna informações da sessão atual (sem linha fixa)."""
        if not self.fiscal_atual or not self.data_atual:
            return None

        try:
            registros = self.listar_registros_sessao_atual()

            # Contar linhas diferentes na sessão
            linhas_unicas = set()
            for registro in registros:
                if len(registro) > 3 and registro[3]:  # linha está na posição 3
                    linhas_unicas.add(registro[3])

            linhas_texto = f"{len(linhas_unicas)} linha(s)" if linhas_unicas else "Nenhuma linha"

            print(f"📊 Sessão atual - Intervalo: {self.intervalo_atual} minutos")
            return {
                'fiscal': self.fiscal_atual,
                'data': self.data_atual,
                'linhas': linhas_texto,
                'total_carros': len(registros),
                'intervalo_atual': self.intervalo_atual,
                'intervalos_por_linha': self.intervalos_por_linha,  # 🆕 NOVO
                'ativa': True
            }
        except Exception as e:
            print(f"❌ Erro ao obter sessão atual: {str(e)}")
            return None

    def finalizar_dia(self):
        """Finaliza o dia atual, salvando todos os dados e limpando a sessão."""
        if not self.fiscal_atual or not self.data_atual:
            print("❌ Nenhuma sessão ativa para finalizar!")
            return {
                'status': 'erro',
                'mensagem': 'Nenhuma sessão ativa para finalizar!'
            }

        try:
            registros_hoje = self.listar_registros_sessao_atual()
            total_registros = len(registros_hoje)

            dados_finalizados = {
                'fiscal': self.fiscal_atual,
                'data': self.data_atual,
                'total_carros': total_registros,
                'registros': registros_hoje
            }

            # Limpar variáveis de sessão
            self.fiscal_atual = None
            self.data_atual = None
            self.linha_atual = None  # Sempre None agora
            self.intervalo_atual = 8  # Resetar para padrão

            # 🆕 NOVO: Resetar intervalos por linha
            self.intervalos_por_linha = {
                'Centro x Vila Verde': 8,
                'Centro x Rasa': 8
            }

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

    # ========== CONSULTAS E ESTATÍSTICAS ==========

    def consultar_por_data(self, data_consulta):
        """Consulta todos os registros de uma data específica - COM STATUS DE CONFIRMAÇÃO."""
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
        """Consulta registros com múltiplos filtros - COM STATUS DE CONFIRMAÇÃO."""
        try:
            conexao = self.connect()
            cursor = conexao.cursor()

            sql = "SELECT * FROM saida_carros WHERE 1=1"
            valores = []

            if filtros.get('data_especifica'):
                sql += " AND DATE(data_trabalho) = %s"
                valores.append(filtros['data_especifica'])

            if filtros.get('data_inicio'):
                sql += " AND DATE(data_trabalho) >= %s"
                valores.append(filtros['data_inicio'])

            if filtros.get('data_fim'):
                sql += " AND DATE(data_trabalho) <= %s"
                valores.append(filtros['data_fim'])

            if filtros.get('fiscal'):
                sql += " AND nome_fiscal LIKE %s"
                valores.append(f"%{filtros['fiscal']}%")

            if filtros.get('linha'):
                sql += " AND linha LIKE %s"
                valores.append(f"%{filtros['linha']}%")

            if filtros.get('numero_carro'):
                sql += " AND numero_carro LIKE %s"
                valores.append(f"%{filtros['numero_carro']}%")

            if filtros.get('nome_motorista'):
                sql += " AND nome_motorista LIKE %s"
                valores.append(f"%{filtros['nome_motorista']}%")

            sql += " ORDER BY data_trabalho DESC, horario_saida ASC"

            cursor.execute(sql, valores)
            resultado = cursor.fetchall()

            cursor.close()
            conexao.close()

            print(f"🔍 Consulta com filtros: {len(resultado)} registros encontrados")
            return resultado

        except Exception as e:
            print(f"❌ Erro ao consultar com filtros: {str(e)}")
            return []

    def obter_estatisticas_periodo(self, data_inicio, data_fim):
        """Retorna estatísticas de um período específico."""
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

    # ========== EDIÇÃO ==========

    def editar_registros(self, id_registro, nome_fiscal, data_trabalho, linha, numero_carro, nome_motorista,
                         horario_saida):
        """Edita um registro existente (agora com linha por carro)"""
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

            # Garantir que horário tenha segundos = 00
            try:
                if isinstance(horario_saida, str):
                    horario_obj = datetime.strptime(horario_saida, '%H:%M').time()
                else:
                    horario_obj = horario_saida

                horario_final = horario_obj.replace(second=0, microsecond=0)
                print(f"🕐 Horário de edição ajustado: {horario_saida} → {horario_final}")

            except Exception as e:
                print(f"❌ Erro ao processar horário na edição: {e}")
                horario_final = horario_saida

            sql = """UPDATE saida_carros 
                     SET nome_fiscal = %s, 
                         data_trabalho = %s, 
                         linha = %s, 
                         numero_carro = %s, 
                         nome_motorista = %s, 
                         horario_saida = %s 
                     WHERE id = %s"""

            valores = (nome_fiscal, data_trabalho, linha, numero_carro, nome_motorista, horario_final, id_registro)

            cursor.execute(sql, valores)
            conexao.commit()

            cursor.close()
            conexao.close()

            print(f"✅ Registro {id_registro} editado com sucesso!")
            return True

        except Exception as e:
            print(f"❌ Erro ao editar registro: {str(e)}")
            return False

    # ========== UTILITÁRIOS ==========

    def executar_migracao_inicial(self):
        """Execute esta função UMA VEZ para preparar o banco de dados"""
        print("🔧 Executando migração do banco de dados...")
        resultado = self.adicionar_coluna_saida_confirmada()

        if resultado:
            print("✅ Migração concluída com sucesso!")
            print("📝 Agora o sistema pode persistir confirmações de saída!")
        else:
            print("❌ Erro na migração!")

        return resultado

    def resetar_todas_confirmacoes(self):
        """CORREÇÃO: Reseta todas as confirmações para FALSE (todos aguardando)"""
        try:
            conexao = self.connect()
            cursor = conexao.cursor()

            sql = "UPDATE saida_carros SET saida_confirmada = FALSE"
            cursor.execute(sql)
            conexao.commit()

            # Contar quantos foram atualizados
            sql_count = "SELECT COUNT(*) FROM saida_carros"
            cursor.execute(sql_count)
            total = cursor.fetchone()[0]

            cursor.close()
            conexao.close()

            print(f"🔄 CORREÇÃO: {total} carros agora estão como 'AGUARDANDO' (saida_confirmada = FALSE)")
            return True

        except Exception as e:
            print(f"❌ Erro ao resetar confirmações: {str(e)}")
            return False

    def obter_intervalo_atual(self):
        """Retorna o intervalo atual definido"""
        return self.intervalo_atual


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
