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
            # Página inicial
            self.servir_arquivo_html()
        elif caminho == '/listar':
            # Retorna dados da sessão atual (não todos os registros)
            self.enviar_lista_carros_sessao()
        elif caminho == '/listar-todos':
            # Retorna TODOS os dados do banco
            self.enviar_lista_carros()
        elif caminho == '/sessao-atual':
            # Retorna informações da sessão atual
            self.enviar_sessao_atual()
        else:
            # Página não encontrada
            self.enviar_erro_404()

    def do_POST(self):
        """Responde a requisições POST (formulários)"""
        caminho = self.path
        tamanho = int(self.headers['Content-Length'])
        dados = self.rfile.read(tamanho).decode('utf-8')

        """os 3 codigos acima (caminho, tamanho, dados) é um bom costume ter na funçõe do_POST das sua aplicações.
        isso pq eles vão ler o tamanho dos dados enviados no formulario e decodifica no padrão UTF-8"""
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
        else:
            self.enviar_erro_404()

    def enviar_pagina_inicial(self):
        """Redireciona para o arquivo HTML"""
        # Em vez de retornar HTML, redireciona para o arquivo
        self.send_response(302)
        self.send_header('Location', '/index.html')
        self.end_headers()

    def servir_arquivo_html(self):
        """Serve o arquivo HTML estático"""
        try:
            with open('index.html', 'r', encoding='utf-8') as arquivo:
                conteudo = arquivo.read()

            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8') #pra eu não esquecer: Define cabeçalho informando que o conteúdo é HTML com UTF-8

            self.end_headers()
            self.wfile.write(conteudo.encode('utf-8'))
        except FileNotFoundError:
            self.send_error(404, "Arquivo index.html não encontrado")

    def enviar_lista_carros(self):
        """Envia lista de carros REAL do banco de dados"""
        print("🔍 DEBUG: Função enviar_lista_carros() chamada")

        try:
            print("🔍 DEBUG: Tentando conectar com banco...")

            # Buscar dados reais do banco - TODOS os registros
            registros = self.db.listar_todos_registros()
            print(f"🔍 DEBUG: Registros encontrados: {len(registros)}")
            print(f"🔍 DEBUG: Primeiros registros: {registros[:2] if registros else 'Nenhum'}")

            if len(registros) == 0:
                print("❌ PROBLEMA: listar_todos_registros() retornou vazio!")
                print("🔧 Testando função diretamente...")
                # Teste direto
                teste = self.db.listar_todos_registros()
                print(f"🔧 Teste direto retornou: {len(teste)} registros")

            # Converter para formato JSON amigável
            carros = []
            for registro in registros:
                print(f"🔍 DEBUG: Processando registro: {registro}")

                # Converter tipos MySQL para strings
                data_trabalho = registro[2].strftime('%Y-%m-%d') if registro[2] else None
                horario_saida = str(registro[6]) if registro[6] else None

                carro = {
                    "id": registro[0],
                    "fiscal": registro[1],
                    "data": data_trabalho,
                    "linha": registro[3],
                    "numero": registro[4],
                    "motorista": registro[5],
                    "horario": horario_saida
                }
                carros.append(carro)

            dados = {
                "status": "ok",
                "total": len(carros),
                "carros": carros
            }

            print(f"🔍 DEBUG: Dados finais: {dados}")

        except Exception as e:
            # Se der erro no banco
            print(f"🔍 DEBUG: ERRO capturado: {str(e)}")
            print(f"🔍 DEBUG: Tipo do erro: {type(e)}")

            dados = {
                "status": "erro",
                "mensagem": f"Erro ao buscar dados: {str(e)}",
                "carros": []
            }

        resposta = json.dumps(dados, ensure_ascii=False)

        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.enviar_cabecalhos_cors()
        self.end_headers()
        self.wfile.write(resposta.encode('utf-8'))

    def processar_remover_carro(self, dados):
        """Remove um carro do banco"""
        try:
            # Converter dados do formulário
            parametros = parse_qs(dados)
            id_carro = parametros.get('id', [''])[0]

            print(f"🗑️ Removendo carro ID: {id_carro}")

            # Remover do banco
            sucesso = self.db.deletar_registro(id_carro)

            if sucesso:
                resposta = {
                    "status": "ok",
                    "mensagem": "Carro removido com sucesso!"
                }
            else:
                resposta = {
                    "status": "erro",
                    "mensagem": "Carro não encontrado!"
                }

        except Exception as e:
            print(f"❌ ERRO ao remover carro: {str(e)}")
            resposta = {
                "status": "erro",
                "mensagem": f"Erro ao remover carro: {str(e)}"
            }

        self.enviar_json(resposta)

    def processar_cabecalho(self, dados):
        """Processa dados do cabeçalho REAL"""
        try:
            # Converter dados do formulário para dicionário
            parametros = parse_qs(dados)

            # Extrair valores (parse_qs retorna listas)
            fiscal = parametros.get('fiscal', [''])[0]
            data = parametros.get('data', [''])[0]
            linha = parametros.get('linha', [''])[0]

            print(f"📋 Cabeçalho recebido: Fiscal={fiscal}, Data={data}, Linha={linha}")

            # Salvar no banco através do DatabaseManager
            self.db.cabecalho_prancheta(fiscal, data, linha)

            resposta = {
                "status": "ok",
                "mensagem": "Cabeçalho definido com sucesso!",
                "dados": {"fiscal": fiscal, "data": data, "linha": linha}
            }

        except Exception as e:
            resposta = {
                "status": "erro",
                "mensagem": f"Erro ao salvar cabeçalho: {str(e)}"
            }

        self.enviar_json(resposta)

    def processar_adicionar_carro(self, dados):
        try:
            parametros = parse_qs(dados)
            numero = parametros.get('numero', [''])[0]
            motorista = parametros.get('motorista', [''])[0]
            horario = parametros.get('horario', [''])[0]

            print(f"🚗 Carro recebido: Número={numero}, Motorista={motorista}, Horário={horario}")

            # Salvar no banco
            resultado = self.db.inserir_dados_motorista(numero, motorista, horario)

            if resultado is False:
                # Cabeçalho não foi definido
                resposta = {
                    "status": "erro",
                    "mensagem": "Defina o cabeçalho antes de adicionar carros!"
                }
            else:
                resposta = {
                    "status": "ok",
                    "mensagem": "Carro adicionado com sucesso!",
                    "dados": {"numero": numero, "motorista": motorista, "horario": horario}
                }

        except Exception as e:
            print(f"❌ ERRO ao adicionar carro: {str(e)}")
            resposta = {
                "status": "erro",
                "mensagem": f"Erro ao adicionar carro: {str(e)}"
            }

        self.enviar_json(resposta)


        # ========== NOVAS ROTAS ==========

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
                    print(f"✅ Dia finalizado: {resultado['dados']['total_carros']} carros")
                else:
                    resposta = {
                        "status": "erro",
                        "mensagem": resultado['mensagem']
                    }
                    print(f"❌ Erro ao finalizar: {resultado['mensagem']}")

            except Exception as e:
                print(f"❌ ERRO ao finalizar dia: {str(e)}")
                resposta = {
                    "status": "erro",
                    "mensagem": f"Erro ao finalizar dia: {str(e)}"
                }

            self.enviar_json(resposta)

    def processar_consultar(self, dados):
            """Processa consultas com filtros"""
            try:
                # Converter dados do formulário
                parametros = parse_qs(dados)

                # Extrair filtros
                filtros = {}

                # Verificar se é consulta por data específica
                if parametros.get('data_especifica', [''])[0]:
                    filtros['data_especifica'] = parametros.get('data_especifica', [''])[0]

                # Ou consulta por período
                if parametros.get('data_inicio', [''])[0]:
                    filtros['data_inicio'] = parametros.get('data_inicio', [''])[0]
                if parametros.get('data_fim', [''])[0]:
                    filtros['data_fim'] = parametros.get('data_fim', [''])[0]

                # Outros filtros opcionais
                if parametros.get('fiscal', [''])[0]:
                    filtros['fiscal'] = parametros.get('fiscal', [''])[0]
                if parametros.get('linha', [''])[0]:
                    filtros['linha'] = parametros.get('linha', [''])[0]
                if parametros.get('numero_carro', [''])[0]:
                    filtros['numero_carro'] = parametros.get('numero_carro', [''])[0]
                if parametros.get('nome_motorista', [''])[0]:
                    filtros['nome_motorista'] = parametros.get('nome_motorista', [''])[0]

                print(f"🔍 Consulta com filtros: {filtros}")

                # Se for apenas consulta por data específica, usar método otimizado
                if len(filtros) == 1 and 'data_especifica' in filtros:
                    registros = self.db.consultar_por_data(filtros['data_especifica'])
                else:
                    # Usar consulta com múltiplos filtros
                    registros = self.db.consultar_por_filtros(filtros)

                # Converter registros para formato JSON
                carros = []
                for registro in registros:
                    # Converter tipos MySQL para strings
                    data_trabalho = registro[2].strftime('%Y-%m-%d') if registro[2] else None
                    horario_saida = str(registro[6]) if registro[6] else None

                    carro = {
                        "id": registro[0],
                        "fiscal": registro[1],
                        "data": data_trabalho,
                        "linha": registro[3],
                        "numero": registro[4],
                        "motorista": registro[5],
                        "horario": horario_saida
                    }
                    carros.append(carro)

                resposta = {
                    "status": "ok",
                    "mensagem": f"Encontrados {len(carros)} registros",
                    "total": len(carros),
                    "carros": carros,
                    "filtros_aplicados": filtros
                }

                print(f"🔍 Consulta finalizada: {len(carros)} registros encontrados")

            except Exception as e:
                print(f"❌ ERRO ao consultar: {str(e)}")
                resposta = {
                    "status": "erro",
                    "mensagem": f"Erro ao consultar dados: {str(e)}",
                    "carros": []
                }

            self.enviar_json(resposta)

    def processar_estatisticas(self, dados):
            """Processa solicitação de estatísticas"""
            try:
                # Converter dados do formulário
                parametros = parse_qs(dados)

                data_inicio = parametros.get('data_inicio', [''])[0]
                data_fim = parametros.get('data_fim', [''])[0]

                print(f"📊 Calculando estatísticas de {data_inicio} a {data_fim}")

                if not data_inicio or not data_fim:
                    resposta = {
                        "status": "erro",
                        "mensagem": "Data de início e fim são obrigatórias"
                    }
                else:
                    estatisticas = self.db.obter_estatisticas_periodo(data_inicio, data_fim)

                    if estatisticas:
                        resposta = {
                            "status": "ok",
                            "mensagem": f"Estatísticas calculadas para o período",
                            "estatisticas": estatisticas
                        }
                    else:
                        resposta = {
                            "status": "erro",
                            "mensagem": "Erro ao calcular estatísticas"
                        }

            except Exception as e:
                print(f"❌ ERRO ao calcular estatísticas: {str(e)}")
                resposta = {
                    "status": "erro",
                    "mensagem": f"Erro ao calcular estatísticas: {str(e)}"
                }

            self.enviar_json(resposta)


    def enviar_sessao_atual(self):
        """Envia informações da sessão atual"""
        try:
            sessao = self.db.obter_sessao_atual()

            if sessao:
                dados = {
                    "status": "ok",
                    "sessao": sessao
                }
            else:
                dados = {
                    "status": "sem_sessao",
                    "mensagem": "Nenhuma sessão ativa",
                    "sessao": None
                }

        except Exception as e:
            dados = {
                "status": "erro",
                "mensagem": f"Erro ao obter sessão: {str(e)}",
                "sessao": None
            }

        self.enviar_json(dados)

    def enviar_lista_carros_sessao(self):
        """Envia lista de carros da SESSÃO ATUAL apenas"""
        print("🔍 DEBUG: Função enviar_lista_carros_sessao() chamada")

        try:
            # Buscar dados apenas da sessão atual
            registros = self.db.listar_registros_sessao_atual()
            print(f"🔍 DEBUG: Registros da sessão atual: {len(registros)}")

            # Converter para formato JSON amigável
            carros = []
            for registro in registros:
                print(f"🔍 DEBUG: Processando registro: {registro}")

                # Converter tipos MySQL para strings
                data_trabalho = registro[2].strftime('%Y-%m-%d') if registro[2] else None
                horario_saida = str(registro[6]) if registro[6] else None

                carro = {
                    "id": registro[0],
                    "fiscal": registro[1],
                    "data": data_trabalho,
                    "linha": registro[3],
                    "numero": registro[4],
                    "motorista": registro[5],
                    "horario": horario_saida
                }
                carros.append(carro)

            dados = {
                "status": "ok",
                "total": len(carros),
                "carros": carros,
                "tipo": "sessao_atual"
            }

            print(f"🔍 DEBUG: Dados da sessão atual: {len(carros)} carros")

        except Exception as e:
            print(f"🔍 DEBUG: ERRO capturado: {str(e)}")

            dados = {
                "status": "erro",
                "mensagem": f"Erro ao buscar dados da sessão: {str(e)}",
                "carros": []
            }

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

            sucesso = self.db.editar_registros(
                id_registro, nome_fiscal, data_trabalho, linha,
                numero_carro, nome_motorista, horario_saida
            )

            if sucesso:
                resposta = {
                    "status": "ok",
                    "mensagem": "Registro editado com sucesso!"
                }
            else:
                resposta = {
                    "status": "erro",
                    "mensagem": "Erro ao editar registro!"
                }

        except Exception as e:
            resposta = {
                "status": "erro",
                "mensagem": f"Erro ao editar: {str(e)}"
            }

        self.enviar_json(resposta)
if __name__ == '__main__':


    PORT = int(os.environ.get('PORT', 8001))

    with socketserver.TCPServer(("0.0.0.0", PORT), MeuServidor) as httpd:
        print(f"🌐 Servidor rodando em http://localhost:{PORT}")
        print("🔥 Aperte Ctrl+C para parar")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Servidor parado!")
