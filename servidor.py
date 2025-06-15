import http.server
import socketserver
from urllib.parse import urlparse, parse_qs
import json
from database import DatabaseManager
import os


class MeuServidor(http.server.BaseHTTPRequestHandler):
    # Instância GLOBAL do DatabaseManager (compartilhada)
    db_global = DatabaseManager()

    def __init__(self, *args, **kwargs):
        # Usar a instância global em vez de criar nova
        self.db = MeuServidor.db_global
        super().__init__(*args, **kwargs)

    def enviar_cabecalhos_cors(self):
        """Adiciona cabeçalhos CORS para permitir requisições do frontend"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        """Responde a requisições OPTIONS (necessário para CORS)"""
        self.send_response(200)
        self.enviar_cabecalhos_cors()
        self.end_headers()

    def enviar_json(self, dados):
        """Envia resposta em JSON"""
        resposta = json.dumps(dados, ensure_ascii=False)

        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.enviar_cabecalhos_cors()
        self.end_headers()
        self.wfile.write(resposta.encode('utf-8'))

    def do_GET(self):
        """Responde a requisições GET (páginas, dados)"""
        caminho = self.path

        if caminho == '/' or caminho == '/index.html':
            # Página inicial - Painel do Presidente
            self.servir_arquivo_html()
        elif caminho == '/motorista':
            # Página do Motorista - Interface Simples
            self.servir_pagina_motorista()
        elif caminho == '/listar':
            # Retorna dados da sessão atual (não todos os registros)
            self.enviar_lista_carros_sessao()
        elif caminho == '/listar-todos':
            # Retorna TODOS os dados do banco
            self.enviar_lista_carros()
        elif caminho == '/sessao-atual':
            # Retorna informações da sessão atual
            self.enviar_sessao_atual()
        elif caminho == '/intervalo-atual':
            # Retorna intervalo atual
            self.enviar_intervalo_atual()
        elif caminho == '/listar-por-linha':
            # 🆕 NOVO: Retorna carros separados por linha
            self.enviar_carros_por_linha()
        elif caminho == '/intervalos-linhas':
            # 🆕 NOVO: Retorna intervalos de todas as linhas
            self.enviar_intervalos_todas_linhas()
        else:
            # Página não encontrada
            self.enviar_erro_404()

    def do_POST(self):
        """Responde a requisições POST (formulários)"""
        caminho = self.path
        tamanho = int(self.headers['Content-Length'])
        dados = self.rfile.read(tamanho).decode('utf-8')

        if caminho == '/cabecalho':
            self.processar_cabecalho(dados)
        elif caminho == '/adicionar':
            self.processar_adicionar_carro(dados)
        elif caminho == '/remover':
            self.processar_remover_carro(dados)
        elif caminho == '/finalizar-dia':
            self.processar_finalizar_dia(dados)
        elif caminho == '/consultar':
            self.processar_consultar(dados)
        elif caminho == '/estatisticas':
            self.processar_estatisticas(dados)
        elif caminho == '/editar':
            self.processar_editar_registro(dados)
        elif caminho == '/confirmar-saida':
            self.processar_confirmar_saida(dados)
        elif caminho == '/definir-intervalo':
            self.processar_definir_intervalo(dados)
        elif caminho == '/adicionar-motorista':
            self.processar_adicionar_motorista(dados)
        elif caminho == '/definir-intervalo-linha':
            # 🆕 NOVO: Define intervalo para linha específica
            self.processar_definir_intervalo_linha(dados)
        else:
            self.enviar_erro_404()

    def enviar_erro_404(self):
        """Envia erro 404"""
        self.send_response(404)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.enviar_cabecalhos_cors()
        self.end_headers()
        self.wfile.write(b'<h1>404 - Pagina nao encontrada</h1>')

    def servir_arquivo_html(self):
        """Serve o arquivo HTML estático do Presidente"""
        try:
            with open('index.html', 'r', encoding='utf-8') as arquivo:
                conteudo = arquivo.read()

            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(conteudo.encode('utf-8'))
        except FileNotFoundError:
            self.send_error(404, "Arquivo index.html não encontrado")

    def servir_pagina_motorista(self):
        """Serve a página do motorista (interface simples)"""
        try:
            with open('motorista.html', 'r', encoding='utf-8') as arquivo:
                conteudo = arquivo.read()

            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(conteudo.encode('utf-8'))
            print("📱 Página do motorista servida")
        except FileNotFoundError:
            self.send_error(404, "Arquivo motorista.html não encontrado")

    def processar_registro_para_json(self, registro):
        """Função centralizada para processar um registro do banco para JSON"""
        # ESTRUTURA CONFIRMADA: 9 colunas
        # (id, nome_fiscal, data_trabalho, linha, numero_carro, nome_motorista, horario_saida, data_registro, saida_confirmada)
        #  0      1             2          3          4              5              6             7                8

        data_trabalho = registro[2].strftime('%Y-%m-%d') if registro[2] else None
        horario_saida = str(registro[6]) if registro[6] else None

        # CORREÇÃO CRÍTICA: Verificar se saída foi confirmada
        saida_confirmada = bool(registro[8]) if len(registro) > 8 and registro[8] is not None else False

        # VERIFICAR HORÁRIO vs HORA ATUAL para status automático
        from datetime import datetime, time
        agora = datetime.now().time()

        # Se tem horário de saída definido, comparar com hora atual
        if registro[6] and isinstance(registro[6], time):
            horario_carro = registro[6]
            horario_passou = agora >= horario_carro
        else:
            horario_passou = False

        # LÓGICA DO STATUS:
        # - Se confirmado manualmente = SAIU
        # - Se não confirmado E horário passou = pode sair (mas ainda aguardando confirmação)
        # - Se não confirmado E horário não passou = aguardando
        status_real = "SAIU" if saida_confirmada else "AGUARDANDO"

        print(f"🔍 DEBUG: Carro {registro[4]} - Confirmado: {saida_confirmada} - Status: {status_real}")

        return {
            "id": registro[0],
            "fiscal": registro[1],
            "data": data_trabalho,
            "linha": registro[3],
            "numero": registro[4],
            "motorista": registro[5],
            "horario": horario_saida,
            "saida_confirmada": saida_confirmada,
            "status": status_real
        }

    def enviar_lista_carros(self):
        """Envia lista de carros REAL do banco de dados"""
        print("🔍 DEBUG: Função enviar_lista_carros() chamada")

        try:
            registros = self.db.listar_todos_registros()
            print(f"🔍 DEBUG: Registros encontrados: {len(registros)}")

            # Converter para formato JSON amigável
            carros = []
            for registro in registros:
                carro = self.processar_registro_para_json(registro)
                carros.append(carro)

            dados = {
                "status": "ok",
                "total": len(carros),
                "carros": carros,
                "intervalo_atual": self.db.obter_intervalo_atual()
            }

        except Exception as e:
            print(f"🔍 DEBUG: ERRO capturado: {str(e)}")
            dados = {
                "status": "erro",
                "mensagem": f"Erro ao buscar dados: {str(e)}",
                "carros": []
            }

        self.enviar_json(dados)

    def enviar_lista_carros_sessao(self):
        """Envia lista de carros da SESSÃO ATUAL apenas - COM STATUS DE CONFIRMAÇÃO"""
        print("🔍 DEBUG: Função enviar_lista_carros_sessao() chamada")

        try:
            # Buscar dados apenas da sessão atual
            registros = self.db.listar_registros_sessao_atual()
            print(f"🔍 DEBUG: Registros da sessão atual: {len(registros)}")

            # Converter para formato JSON amigável
            carros = []
            for registro in registros:
                print(f"🔍 DEBUG: Processando registro: {registro}")
                carro = self.processar_registro_para_json(registro)
                carros.append(carro)

            # Contar confirmados para debug
            confirmados = sum(1 for c in carros if c['saida_confirmada'])
            print(f"🔍 DEBUG: Carros confirmados: {confirmados}")

            dados = {
                "status": "ok",
                "total": len(carros),
                "carros": carros,
                "tipo": "sessao_atual",
                "intervalo_atual": self.db.obter_intervalo_atual()
            }

        except Exception as e:
            print(f"🔍 DEBUG: ERRO capturado: {str(e)}")
            dados = {
                "status": "erro",
                "mensagem": f"Erro ao buscar dados da sessão: {str(e)}",
                "carros": []
            }

        self.enviar_json(dados)

    def enviar_carros_por_linha(self):
        """🆕 NOVO: Envia carros da sessão atual SEPARADOS por linha"""
        print("🔍 DEBUG: Função enviar_carros_por_linha() chamada")

        try:
            carros_por_linha_raw = self.db.listar_carros_por_linha()

            # Processar cada linha
            carros_por_linha = {}
            total_carros = 0

            for linha, registros in carros_por_linha_raw.items():
                carros_linha = []
                for registro in registros:
                    carro = self.processar_registro_para_json(registro)
                    carros_linha.append(carro)

                carros_por_linha[linha] = {
                    "carros": carros_linha,
                    "total": len(carros_linha),
                    "intervalo": self.db.obter_intervalo_linha(linha)
                }
                total_carros += len(carros_linha)

            dados = {
                "status": "ok",
                "total_geral": total_carros,
                "carros_por_linha": carros_por_linha,
                "tipo": "separado_por_linha"
            }

            print(f"🔍 DEBUG: Carros por linha processados:")
            for linha, info in carros_por_linha.items():
                print(f"    {linha}: {info['total']} carros (intervalo {info['intervalo']}min)")

        except Exception as e:
            print(f"🔍 DEBUG: ERRO ao separar carros por linha: {str(e)}")
            dados = {
                "status": "erro",
                "mensagem": f"Erro ao buscar carros por linha: {str(e)}",
                "carros_por_linha": {}
            }

        self.enviar_json(dados)

    def enviar_intervalos_todas_linhas(self):
        """🆕 NOVO: Envia intervalos específicos de todas as linhas"""
        try:
            intervalos = {}

            # Linhas conhecidas
            linhas_conhecidas = ['Centro x Vila Verde', 'Centro x Rasa']

            for linha in linhas_conhecidas:
                intervalos[linha] = self.db.obter_intervalo_linha(linha)

            dados = {
                "status": "ok",
                "intervalos": intervalos,
                "intervalo_geral": self.db.obter_intervalo_atual()
            }

            print(f"📤 Enviando intervalos por linha: {intervalos}")

        except Exception as e:
            print(f"❌ Erro ao obter intervalos das linhas: {str(e)}")
            dados = {
                "status": "erro",
                "mensagem": f"Erro ao obter intervalos: {str(e)}"
            }

        self.enviar_json(dados)

    def processar_definir_intervalo_linha(self, dados):
        """🆕 NOVO: Processa definição de intervalo para linha específica"""
        try:
            parametros = parse_qs(dados)
            linha = parametros.get('linha', [''])[0]
            novo_intervalo = int(parametros.get('intervalo', ['0'])[0])

            print(f"⏱️ RECEBIDO: Definindo intervalo para linha '{linha}': {novo_intervalo} minutos")

            if not linha:
                resposta = {"status": "erro", "mensagem": "Linha não especificada"}
            else:
                resultado = self.db.definir_intervalo_linha(linha, novo_intervalo)

                if resultado['status'] == 'sucesso':
                    resposta = {
                        "status": "ok",
                        "mensagem": resultado['mensagem'],
                        "linha": resultado['linha'],
                        "intervalo_antigo": resultado['intervalo_antigo'],
                        "intervalo_novo": resultado['intervalo_novo'],
                        "carros_atualizados": resultado['carros_atualizados']
                    }
                    print(
                        f"✅ Intervalo da linha '{linha}' definido: {novo_intervalo} min, {resultado['carros_atualizados']} carros atualizados")
                else:
                    resposta = {"status": "erro", "mensagem": resultado['mensagem']}
                    print(f"❌ Erro ao definir intervalo da linha '{linha}': {resultado['mensagem']}")

        except ValueError:
            resposta = {"status": "erro", "mensagem": "Intervalo deve ser um número válido"}
            print("❌ Erro: Intervalo não é um número válido")
        except Exception as e:
            print(f"❌ ERRO CRÍTICO ao definir intervalo da linha: {str(e)}")
            resposta = {"status": "erro", "mensagem": f"Erro ao definir intervalo da linha: {str(e)}"}

        self.enviar_json(resposta)

    def processar_cabecalho(self, dados):
        """Processa dados do cabeçalho SIMPLIFICADO (só fiscal + data)"""
        try:
            parametros = parse_qs(dados)
            fiscal = parametros.get('fiscal', [''])[0]
            data = parametros.get('data', [''])[0]

            print(f"📋 Cabeçalho recebido: Fiscal={fiscal}, Data={data}")
            self.db.cabecalho_prancheta(fiscal, data)

            resposta = {
                "status": "ok",
                "mensagem": "Cabeçalho definido com sucesso!",
                "dados": {"fiscal": fiscal, "data": data}
            }

        except Exception as e:
            print(f"❌ ERRO ao processar cabeçalho: {str(e)}")
            resposta = {"status": "erro", "mensagem": f"Erro ao salvar cabeçalho: {str(e)}"}

        self.enviar_json(resposta)

    def processar_adicionar_carro(self, dados):
        """Processa adição de carro com logs detalhados"""
        try:
            parametros = parse_qs(dados)
            numero = parametros.get('numero', [''])[0]
            motorista = parametros.get('motorista', [''])[0]
            linha = parametros.get('linha', [''])[0]

            print(f"🚗 RECEBIDO: Número={numero}, Motorista={motorista}, Linha={linha}")

            # Verificar se cabeçalho está definido
            if not self.db.fiscal_atual or not self.db.data_atual:
                print(f"❌ Cabeçalho não definido! Fiscal: {self.db.fiscal_atual}, Data: {self.db.data_atual}")
                resposta = {"status": "erro", "mensagem": "Defina o cabeçalho antes de adicionar carros!"}
                self.enviar_json(resposta)
                return

            # Inserir com horário automático POR LINHA
            print(f"🔄 Chamando inserir_dados_motorista...")
            resultado = self.db.inserir_dados_motorista(numero, motorista, linha)
            print(f"🔄 Resultado do banco: {resultado}")

            if resultado is False:
                print(f"❌ Falha na inserção no banco")
                resposta = {"status": "erro", "mensagem": "Erro ao inserir no banco de dados!"}
            else:
                # Buscar o horário que foi calculado POR LINHA
                horario_calculado = self.db.calcular_proximo_horario_linha(linha)
                print(f"✅ Carro inserido com sucesso! Horário calculado para linha {linha}: {horario_calculado}")

                resposta = {
                    "status": "ok",
                    "mensagem": f"Carro adicionado com sucesso! Horário calculado automaticamente para linha {linha}.",
                    "dados": {
                        "numero": numero,
                        "motorista": motorista,
                        "linha": linha,
                        "horario": str(horario_calculado)[:5] if horario_calculado else "N/A"
                    }
                }

            print(f"📤 Enviando resposta: {resposta}")
            self.enviar_json(resposta)

        except Exception as e:
            print(f"❌ ERRO CRÍTICO ao adicionar carro: {str(e)}")
            import traceback
            traceback.print_exc()

            resposta = {
                "status": "erro",
                "mensagem": f"Erro interno do servidor: {str(e)}"
            }
            self.enviar_json(resposta)

    def processar_remover_carro(self, dados):
        """Remove um carro do banco"""
        try:
            parametros = parse_qs(dados)
            id_carro = parametros.get('id', [''])[0]

            print(f"🗑️ Removendo carro ID: {id_carro}")
            sucesso = self.db.deletar_registro(id_carro)

            if sucesso:
                resposta = {"status": "ok", "mensagem": "Carro removido com sucesso!"}
            else:
                resposta = {"status": "erro", "mensagem": "Carro não encontrado!"}

        except Exception as e:
            print(f"❌ ERRO ao remover carro: {str(e)}")
            resposta = {"status": "erro", "mensagem": f"Erro ao remover carro: {str(e)}"}

        self.enviar_json(resposta)

    def processar_confirmar_saida(self, dados):
        """Processa confirmação AUTOMÁTICA de saída de um carro"""
        try:
            parametros = parse_qs(dados)
            id_carro = parametros.get('id', [''])[0]

            print(f"✅ Confirmando saída AUTOMÁTICA do carro ID: {id_carro}")
            sucesso = self.db.confirmar_saida_carro(id_carro)

            if sucesso:
                resposta = {
                    "status": "ok",
                    "mensagem": "Saída confirmada automaticamente!",
                    "carro_id": id_carro
                }
                print(f"✅ Saída confirmada automaticamente para carro ID: {id_carro}")
            else:
                resposta = {"status": "erro", "mensagem": "Erro ao confirmar saída - carro não encontrado!"}

        except Exception as e:
            print(f"❌ ERRO ao confirmar saída: {str(e)}")
            resposta = {"status": "erro", "mensagem": f"Erro ao confirmar saída: {str(e)}"}

        self.enviar_json(resposta)

    def processar_definir_intervalo(self, dados):
        """Processa definição de novo intervalo entre carros (FUNÇÃO ORIGINAL MANTIDA)"""
        try:
            parametros = parse_qs(dados)
            novo_intervalo = int(parametros.get('intervalo', ['0'])[0])

            print(f"⏱️ RECEBIDO: Definindo novo intervalo GERAL: {novo_intervalo} minutos")
            print(f"⏱️ ANTES: Intervalo atual era: {self.db.obter_intervalo_atual()} minutos")

            resultado = self.db.definir_intervalo(novo_intervalo)

            print(f"⏱️ DEPOIS: Intervalo atual agora é: {self.db.obter_intervalo_atual()} minutos")

            if resultado['status'] == 'sucesso':
                resposta = {
                    "status": "ok",
                    "mensagem": resultado['mensagem'],
                    "intervalo": resultado['intervalo'],
                    "carros_atualizados": resultado['carros_atualizados']
                }
                print(
                    f"✅ Intervalo GERAL definido com sucesso: {novo_intervalo} min, {resultado['carros_atualizados']} carros atualizados")
            else:
                resposta = {"status": "erro", "mensagem": resultado['mensagem']}
                print(f"❌ Erro ao definir intervalo GERAL: {resultado['mensagem']}")

        except Exception as e:
            print(f"❌ ERRO CRÍTICO ao definir intervalo GERAL: {str(e)}")
            resposta = {"status": "erro", "mensagem": f"Erro ao definir intervalo: {str(e)}"}

        self.enviar_json(resposta)

    def enviar_intervalo_atual(self):
        """Envia o intervalo atual definido"""
        try:
            intervalo = self.db.obter_intervalo_atual()
            dados = {
                "status": "ok",
                "intervalo": intervalo
            }
            print(f"📤 Enviando intervalo atual: {intervalo} minutos")
        except Exception as e:
            print(f"❌ Erro ao obter intervalo: {str(e)}")
            dados = {
                "status": "erro",
                "mensagem": f"Erro ao obter intervalo: {str(e)}"
            }

        self.enviar_json(dados)

    def processar_finalizar_dia(self, dados):
        """Processa finalização do dia"""
        try:
            print("🏁 Finalizando dia...")
            resultado = self.db.finalizar_dia()

            if resultado['status'] == 'sucesso':
                resposta = {
                    "status": "ok",
                    "mensagem": resultado['mensagem'],
                    "dados": resultado['dados']
                }
            else:
                resposta = {"status": "erro", "mensagem": resultado['mensagem']}

        except Exception as e:
            print(f"❌ ERRO ao finalizar dia: {str(e)}")
            resposta = {"status": "erro", "mensagem": f"Erro ao finalizar dia: {str(e)}"}

        self.enviar_json(resposta)

    def processar_consultar(self, dados):
        """Processa consultas com filtros"""
        try:
            parametros = parse_qs(dados)
            filtros = {}

            if parametros.get('data_especifica', [''])[0]:
                filtros['data_especifica'] = parametros.get('data_especifica', [''])[0]
            if parametros.get('data_inicio', [''])[0]:
                filtros['data_inicio'] = parametros.get('data_inicio', [''])[0]
            if parametros.get('data_fim', [''])[0]:
                filtros['data_fim'] = parametros.get('data_fim', [''])[0]
            if parametros.get('fiscal', [''])[0]:
                filtros['fiscal'] = parametros.get('fiscal', [''])[0]
            if parametros.get('linha', [''])[0]:
                filtros['linha'] = parametros.get('linha', [''])[0]
            if parametros.get('numero_carro', [''])[0]:
                filtros['numero_carro'] = parametros.get('numero_carro', [''])[0]
            if parametros.get('nome_motorista', [''])[0]:
                filtros['nome_motorista'] = parametros.get('nome_motorista', [''])[0]

            if len(filtros) == 1 and 'data_especifica' in filtros:
                registros = self.db.consultar_por_data(filtros['data_especifica'])
            else:
                registros = self.db.consultar_por_filtros(filtros)

            carros = []
            for registro in registros:
                carro = self.processar_registro_para_json(registro)
                carros.append(carro)

            resposta = {
                "status": "ok",
                "mensagem": f"Encontrados {len(carros)} registros",
                "total": len(carros),
                "carros": carros,
                "filtros_aplicados": filtros
            }

        except Exception as e:
            print(f"❌ ERRO ao consultar: {str(e)}")
            resposta = {"status": "erro", "mensagem": f"Erro ao consultar dados: {str(e)}", "carros": []}

        self.enviar_json(resposta)

    def processar_estatisticas(self, dados):
        """Processa solicitação de estatísticas"""
        try:
            parametros = parse_qs(dados)
            data_inicio = parametros.get('data_inicio', [''])[0]
            data_fim = parametros.get('data_fim', [''])[0]

            if not data_inicio or not data_fim:
                resposta = {"status": "erro", "mensagem": "Data de início e fim são obrigatórias"}
            else:
                estatisticas = self.db.obter_estatisticas_periodo(data_inicio, data_fim)
                if estatisticas:
                    resposta = {"status": "ok", "mensagem": f"Estatísticas calculadas para o período",
                                "estatisticas": estatisticas}
                else:
                    resposta = {"status": "erro", "mensagem": "Erro ao calcular estatísticas"}

        except Exception as e:
            print(f"❌ ERRO ao calcular estatísticas: {str(e)}")
            resposta = {"status": "erro", "mensagem": f"Erro ao calcular estatísticas: {str(e)}"}

        self.enviar_json(resposta)

    def enviar_sessao_atual(self):
        """Envia informações da sessão atual"""
        try:
            sessao = self.db.obter_sessao_atual()
            if sessao:
                dados = {"status": "ok", "sessao": sessao}
                print(f"📤 Enviando sessão atual: {sessao['fiscal']} - {sessao['data']} - {sessao['linhas']}")
            else:
                dados = {"status": "sem_sessao", "mensagem": "Nenhuma sessão ativa", "sessao": None}
                print("📤 Nenhuma sessão ativa")
        except Exception as e:
            print(f"❌ Erro ao obter sessão: {str(e)}")
            dados = {"status": "erro", "mensagem": f"Erro ao obter sessão: {str(e)}", "sessao": None}

        self.enviar_json(dados)

    def processar_editar_registro(self, dados):
        """Processa edição de um registro"""
        try:
            parametros = parse_qs(dados)
            id_registro = parametros.get('id', [''])[0]
            nome_fiscal = parametros.get('nome_fiscal', [''])[0]
            data_trabalho = parametros.get('data_trabalho', [''])[0]
            linha = parametros.get('linha', [''])[0]
            numero_carro = parametros.get('numero_carro', [''])[0]
            nome_motorista = parametros.get('nome_motorista', [''])[0]
            horario_saida = parametros.get('horario_saida', [''])[0]

            print(f"✏️ Editando registro ID: {id_registro}")
            print(f"✏️ Novos dados: {numero_carro} - {nome_motorista} - {linha} - {horario_saida}")

            sucesso = self.db.editar_registros(
                id_registro, nome_fiscal, data_trabalho, linha,
                numero_carro, nome_motorista, horario_saida
            )

            if sucesso:
                resposta = {"status": "ok", "mensagem": "Registro editado com sucesso!"}
            else:
                resposta = {"status": "erro", "mensagem": "Erro ao editar registro!"}

        except Exception as e:
            print(f"❌ ERRO ao editar: {str(e)}")
            resposta = {"status": "erro", "mensagem": f"Erro ao editar: {str(e)}"}

        self.enviar_json(resposta)

    def processar_adicionar_motorista(self, dados):
        """Processa adição de carro VIA MOTORISTA (mesmo que adicionar normal, mas com log diferente)"""
        try:
            parametros = parse_qs(dados)
            numero = parametros.get('numero', [''])[0]
            motorista = parametros.get('motorista', [''])[0]
            linha = parametros.get('linha', [''])[0]

            print(f"🚗 MOTORISTA CADASTRANDO: Número={numero}, Motorista={motorista}, Linha={linha}")

            # Usar a mesma função do banco (inserir_dados_motorista) - agora com horários por linha
            resultado = self.db.inserir_dados_motorista(numero, motorista, linha)

            if resultado is False:
                resposta = {
                    "status": "erro",
                    "mensagem": "Sistema ainda não foi inicializado pelo presidente! Procure o fiscal."
                }
            else:
                # Calcular horário que foi definido PARA A LINHA ESPECÍFICA
                horario_calculado = self.db.calcular_proximo_horario_linha(linha)
                resposta = {
                    "status": "ok",
                    "mensagem": f"Carro {numero} cadastrado com sucesso na linha {linha}!",
                    "horario": str(horario_calculado)[:5],  # Formato HH:MM
                    "dados": {"numero": numero, "motorista": motorista, "linha": linha}
                }
                print(f"✅ MOTORISTA: Carro {numero} cadastrado para linha {linha} às {horario_calculado}")

        except Exception as e:
            print(f"❌ ERRO MOTORISTA ao adicionar carro: {str(e)}")
            resposta = {
                "status": "erro",
                "mensagem": f"Erro no sistema. Procure o fiscal responsável. (Erro: {str(e)})"
            }

        self.enviar_json(resposta)


if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 8001))

    with socketserver.TCPServer(("0.0.0.0", PORT), MeuServidor) as httpd:
        print(f"🌐 Servidor rodando em http://localhost:{PORT}")
        print("🔥 Aperte Ctrl+C para parar")
        print("")
        print("📍 PÁGINAS DISPONÍVEIS:")
        print(f"   👑 PRESIDENTE: http://localhost:{PORT}/")
        print(f"   🚗 MOTORISTA:  http://localhost:{PORT}/motorista")
        '''print("")
        print("✅ FUNCIONALIDADES ATIVAS:")
        print("   📋 Cabeçalho simplificado (fiscal + data)")
        print("   🚗 Adição de carros com horário automático POR LINHA")
        print("   ⚙️ Controle de intervalo dinâmico POR LINHA")
        print("   ⏰ Confirmação automática de saída")
        print("   📊 Consultas e estatísticas por linha")
        print("   🚐 Interface separada para motoristas")
        print("   🆕 Gestão independente de intervalos por linha")
        print("")
        print("🆕 NOVOS ENDPOINTS:")
        print("   GET  /listar-por-linha       → Carros separados por linha")
        print("   GET  /intervalos-linhas      → Intervalos de cada linha")
        print("   POST /definir-intervalo-linha → Define intervalo específico")'''

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Servidor parado!")
