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
        elif caminho == '/confirmar-saida':  # NOVA ROTA
            self.processar_confirmar_saida(dados)
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
        """Serve o arquivo HTML estático"""
        try:
            with open('index.html', 'r', encoding='utf-8') as arquivo:
                conteudo = arquivo.read()

            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(conteudo.encode('utf-8'))
        except FileNotFoundError:
            self.send_error(404, "Arquivo index.html não encontrado")

    def processar_registro_para_json(self, registro):
        """Função centralizada para processar um registro do banco para JSON"""
        # ESTRUTURA CONFIRMADA: 9 colunas
        # (id, nome_fiscal, data_trabalho, linha, numero_carro, nome_motorista, horario_saida, data_registro, saida_confirmada)
        #  0      1             2          3          4              5              6             7                8

        data_trabalho = registro[2].strftime('%Y-%m-%d') if registro[2] else None
        horario_saida = str(registro[6]) if registro[6] else None

        # CORREÇÃO PRINCIPAL: saida_confirmada está na posição 8
        saida_confirmada = bool(registro[8]) if len(registro) > 8 else False

        print(
            f"🔍 NOVO DEBUG: ID={registro[0]}, Carro={registro[4]}, Posição[8]={registro[8] if len(registro) > 8 else 'N/A'}, Confirmado={saida_confirmada}")

        return {
            "id": registro[0],
            "fiscal": registro[1],
            "data": data_trabalho,
            "linha": registro[3],
            "numero": registro[4],
            "motorista": registro[5],
            "horario": horario_saida,
            "saida_confirmada": saida_confirmada
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
                "carros": carros
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
                "tipo": "sessao_atual"
            }

        except Exception as e:
            print(f"🔍 DEBUG: ERRO capturado: {str(e)}")
            dados = {
                "status": "erro",
                "mensagem": f"Erro ao buscar dados da sessão: {str(e)}",
                "carros": []
            }

        self.enviar_json(dados)

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

    def processar_cabecalho(self, dados):
        """Processa dados do cabeçalho REAL"""
        try:
            parametros = parse_qs(dados)
            fiscal = parametros.get('fiscal', [''])[0]
            data = parametros.get('data', [''])[0]
            linha = parametros.get('linha', [''])[0]

            print(f"📋 Cabeçalho recebido: Fiscal={fiscal}, Data={data}, Linha={linha}")
            self.db.cabecalho_prancheta(fiscal, data, linha)

            resposta = {
                "status": "ok",
                "mensagem": "Cabeçalho definido com sucesso!",
                "dados": {"fiscal": fiscal, "data": data, "linha": linha}
            }

        except Exception as e:
            resposta = {"status": "erro", "mensagem": f"Erro ao salvar cabeçalho: {str(e)}"}

        self.enviar_json(resposta)

    def processar_adicionar_carro(self, dados):
        try:
            parametros = parse_qs(dados)
            numero = parametros.get('numero', [''])[0]
            motorista = parametros.get('motorista', [''])[0]
            horario = parametros.get('horario', [''])[0]

            print(f"🚗 Carro recebido: Número={numero}, Motorista={motorista}, Horário={horario}")
            resultado = self.db.inserir_dados_motorista(numero, motorista, horario)

            if resultado is False:
                resposta = {"status": "erro", "mensagem": "Defina o cabeçalho antes de adicionar carros!"}
            else:
                resposta = {
                    "status": "ok",
                    "mensagem": "Carro adicionado com sucesso!",
                    "dados": {"numero": numero, "motorista": motorista, "horario": horario}
                }

        except Exception as e:
            print(f"❌ ERRO ao adicionar carro: {str(e)}")
            resposta = {"status": "erro", "mensagem": f"Erro ao adicionar carro: {str(e)}"}

        self.enviar_json(resposta)

    def processar_confirmar_saida(self, dados):
        """Processa confirmação de saída de um carro"""
        try:
            parametros = parse_qs(dados)
            id_carro = parametros.get('id', [''])[0]

            print(f"✅ Confirmando saída do carro ID: {id_carro}")
            sucesso = self.db.confirmar_saida_carro(id_carro)

            if sucesso:
                resposta = {
                    "status": "ok",
                    "mensagem": "Saída confirmada com sucesso!",
                    "carro_id": id_carro
                }
                print(f"✅ Saída confirmada para carro ID: {id_carro}")
            else:
                resposta = {"status": "erro", "mensagem": "Erro ao confirmar saída - carro não encontrado!"}

        except Exception as e:
            print(f"❌ ERRO ao confirmar saída: {str(e)}")
            resposta = {"status": "erro", "mensagem": f"Erro ao confirmar saída: {str(e)}"}

        self.enviar_json(resposta)

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
            resposta = {"status": "erro", "mensagem": f"Erro ao calcular estatísticas: {str(e)}"}

        self.enviar_json(resposta)

    def enviar_sessao_atual(self):
        """Envia informações da sessão atual"""
        try:
            sessao = self.db.obter_sessao_atual()
            if sessao:
                dados = {"status": "ok", "sessao": sessao}
            else:
                dados = {"status": "sem_sessao", "mensagem": "Nenhuma sessão ativa", "sessao": None}
        except Exception as e:
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

            sucesso = self.db.editar_registros(
                id_registro, nome_fiscal, data_trabalho, linha,
                numero_carro, nome_motorista, horario_saida
            )

            if sucesso:
                resposta = {"status": "ok", "mensagem": "Registro editado com sucesso!"}
            else:
                resposta = {"status": "erro", "mensagem": "Erro ao editar registro!"}

        except Exception as e:
            resposta = {"status": "erro", "mensagem": f"Erro ao editar: {str(e)}"}

        self.enviar_json(resposta)


if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 8001))

    with socketserver.TCPServer(("0.0.0.0", PORT), MeuServidor) as httpd:
        print(f"🌐 Servidor rodando em http://localhost:{PORT}")
        print("🔥 Aperte Ctrl+C para parar")
        print("✅ CORREÇÃO APLICADA: Campo saida_confirmada na posição correta!")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Servidor parado!")
