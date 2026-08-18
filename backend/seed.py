"""Carga inicial de dados ficticios para testes.

Executada no lifespan de startup da aplicacao. Idempotente: so cria
registros quando as tabelas envolvidas estao vazias.

SEGURANCA: so roda quando SEED_DEMO=1 (dev local). Em producao, deixe
vazio e use o endpoint /api/auth/setup para criar o primeiro admin.
"""
import os
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from auth import hash_password
from models import User, Cliente, ClienteEndereco, ClienteContato

logger = logging.getLogger(__name__)

SEED_DEMO = os.getenv("SEED_DEMO", "").strip() == "1"

# Credenciais do admin ficticio para testes locais
ADMIN_EMAIL = "admin@app.com"
ADMIN_PASSWORD = "admin123"
ADMIN_NAME = "Administrador Teste"

# Usuarios de exemplo com permissoes diferentes (email, nome, senha, permissoes, empresa)
_USUARIOS_EXEMPLO = [
    ("vis@app.com",   "Visualizador Demo", "vis123",   ["visualizar"],                       "SIN"),
    ("editor@app.com","Editor Demo",       "edit123",  ["visualizar", "editar"],             "AC"),
    ("full@app.com",  "Cadastros Demo",    "full123",  ["visualizar", "editar", "criar", "exportar", "solicitacoes"], "SIN"),
    ("aprov@app.com", "Aprovador Demo",     "aprov123", ["visualizar", "aprovar"],            "AC"),
    ("gest@app.com",  "Gestor Demo",       "gest123",  ["visualizar", "editar", "criar", "deletar", "carga", "exportar", "aprovar", "solicitacoes"], "SIN"),
]


# (codigo, nome, telefone, contato, cep, rua, numero, bairro, cidade, uf, lat, lon)
_CLIENTES_FICTICIOS = [
    ("C001", "Supermercado Bom Preco",  "(11) 9 8888-1111", "Joao Silva",     "01000-000", "Av. Paulista",                "1500", "Bela Vista",      "Sao Paulo",      "SP", -23.561414, -46.656015),
    ("C002", "Padaria Pao Quente",       "(11) 9 7777-2222", "Maria Souza",     "02010-000", "R. Augusta",                  "220",  "Consolacao",      "Sao Paulo",      "SP", -23.552450, -46.658240),
    ("C003", "Farmacia Vida Saudavel",   "(11) 9 6666-3333", "Carlos Lima",     "03020-010", "R. Vergueiro",                "985",  "Liberdade",       "Sao Paulo",      "SP", -23.564300, -46.636800),
    ("C004", "Mercadinho Estrela",       "(11) 9 5555-4444", "Ana Pereira",     "04001-000", "R. Joaquim Floriano",         "120",  "Vila Mariana",    "Sao Paulo",      "SP", -23.587400, -46.638600),
    ("C005", "Acougue Corte Nobre",      "(11) 9 4444-5555", "Pedro Alves",     "05010-000", "R. Carapicuiba",              "340",  "Perdizes",        "Sao Paulo",      "SP", -23.549500, -46.687900),
    ("C006", "Restaurante Sabor Caseiro","(11) 9 3333-6666", "Lucia Fernandes", "07000-000", "R. Cantareira",               "510",  "Centro",          "Sao Paulo",      "SP", -23.537500, -46.633000),
    ("C007", "Loja Presente & Cia",      "(11) 9 2222-7777", "Roberto Dias",    "01310-000", "Av. Brigadeiro",              "2400", "Jardim Paulista", "Sao Paulo",      "SP", -23.570500, -46.660500),

    ("C008", "Mercadinho Rio Centro",    "(21) 9 9111-1000", "Fabio Andrade",   "20000-000", "R. do Ouvidor",               "210",  "Centro",          "Rio de Janeiro", "RJ", -22.903500, -43.174400),
    ("C009", "Papelaria Universitaria",  "(21) 9 9222-2000", "Sandra Mello",    "20200-010", "R. Vinhedo",                  "88",   "Centro",          "Rio de Janeiro", "RJ", -22.914800, -43.182900),
    ("C010", "Cafe Aurora",              "(21) 9 9333-3000", "Marcos Reis",     "22040-001", "R. Voluntarios",              "305",  "Botafogo",        "Rio de Janeiro", "RJ", -22.953200, -43.188600),
    ("C011", "Bazar Sempre Barato",       "(21) 9 9444-4000", "Cristina Rocha",  "22260-050", "R. Humaita",                  "415",  "Humaita",         "Rio de Janeiro", "RJ", -22.947000, -43.187500),
    ("C012", "Quitanda Natural Mix",     "(21) 9 9555-5000", "Teo Cardoso",     "22410-010", "R. Marques de Sao Vicente",   "70",   "Givea",           "Rio de Janeiro", "RJ", -22.971400, -43.229800),

    ("C013", "Boticario Garden",          "(31) 9 8888-1212", "Pamela Nunes",    "30130-100", "Av. Afonso Pena",             "850",  "Centro",          "Belo Horizonte", "MG", -19.922700, -43.950200),
    ("C014", "Pizzaria Forno de Pedra",  "(31) 9 9777-2323", "Beto Cabral",     "30310-300", "R. da Bahia",                 "612",  "Lourdes",         "Belo Horizonte", "MG", -19.939900, -43.945900),
    ("C015", "Hortifruti Manha Fresca",  "(31) 9 9666-3434", "Renata Pinto",    "31255-010", "R. Prof Otavio Coelho",       "210",  "Sao Lucas",       "Belo Horizonte", "MG", -19.874400, -43.913000),
    ("C016", "Pet Shop Amigo Fiel",       "(31) 9 9555-4545", "Gustavo Brito",   "30565-000", "R. Prof Jose Vieira",         "1400", "Cidade Nova",     "Belo Horizonte", "MG", -19.917900, -43.981200),
    ("C017", "Distribuidora Sudeste Ltda","(31) 9 9444-5656", "Igor Camargo",    "31150-220", "R. Itajuba",                  "2330", "Santa Ines",      "Belo Horizonte", "MG", -19.854600, -43.924800),

    ("C018", "Mercantil Porto Belo",      "(41) 9 9000-1010", "Helena Vaz",      "80010-000", "R. das Flores",               "95",   "Centro",          "Curitiba",       "PR", -25.429500, -49.272600),
    ("C019", "Lava-Jato Brilho Total",    "(41) 9 9111-2020", "Davi Rocha",      "80230-010", "R. Marechal Deodoro",         "1230", "Centro Civico",   "Curitiba",       "PR", -25.430600, -49.268100),
    ("C020", "Floricultura Jardim Real",  "(41) 9 9222-3030", "Sonia Prado",     "81280-020", "R. Alberto Faria",            "410",  "Cajuru",          "Curitiba",       "PR", -25.470700, -49.219700),
    ("C021", "Auto Pecas Veloz",          "(41) 9 9333-4040", "Murilo Cardoso",  "81310-000", "R. Ubaldino de Assis",        "770",  "Boqueirao",       "Curitiba",       "PR", -25.508300, -49.248200),

    ("C022", "Restaurante Sertao Sabores","(71) 9 9876-5050", "Lina Maranhao",   "40020-000", "R. Chile",                    "340",  "Comercio",        "Salvador",       "BA", -12.973100, -38.506700),
    ("C023", "Loja Mar Azul Confeccoes", "(71) 9 9654-6060", "Bruno Mascarenhas","40060-090", "R. Carlos Gomes",             "540",  "Centro",          "Salvador",       "BA", -12.964900, -38.511900),
    ("C024", "Farmacia Sao Cosme",        "(71) 9 9432-7070", "Cleide Tavares",  "40440-010", "R. da Graca",                 "180",  "Calcada",         "Salvador",       "BA", -12.943800, -38.493400),

    ("C025", "Panificadora Trigo Dourado","(51) 9 9696-8080", "Otavio Neto",     "90010-000", "R. dos Andradas",             "1234", "Centro Historico","Porto Alegre",   "RS", -30.028300, -51.227900),
    ("C026", "Atacadao Sul Distribuidora","(51) 9 9585-9090", "Vera Lucia",     "90680-010", "Av. Bento Goncalves",         "3310", "Partenon",        "Porto Alegre",   "RS", -30.061700, -51.192500),
    ("C027", "Agro Mercosul Insumos",     "(51) 9 9474-1010", "Adriano Maciel",  "91740-010", "Av. Salsadus",                "270",  "Cavalhada",       "Porto Alegre",   "RS", -30.095600, -51.233300),

    ("C028", "Lanchonete Sabor da Terra","(62) 9 9998-4040", "Rosa Mendes",     "74020-010", "R. 9",                        "1150", "Centro",          "Goiania",        "GO", -16.680600, -49.273900),
    ("C029", "Material de Construcao Aco & Cimento", "(62) 9 9876-5050", "Tadeu Siqueira", "74830-010", "Av. T-9",        "1440", "Setor Bueno",     "Goiania",        "GO", -16.724000, -49.249700),
    ("C030", "Refrigeracao Polar",        "(62) 9 9754-6060", "Ilda Barros",     "74560-010", "R. C-12",                     "620",  "Setor Marista",   "Goiania",        "GO", -16.714800, -49.263400),

    ("C031", "Supermercado Esperanca",    "(85) 9 9555-7070", "Joana Freitas",   "60015-010", "R. Major Facundo",            "890",  "Centro",          "Fortaleza",      "CE", -3.726700,  -38.526500),
    ("C032", "Loja de Eletronicos Voltagem","(85) 9 9444-8080","Edu Galvao",     "60185-010", "Av. Santos Dumont",           "2210", "Aldeota",         "Fortaleza",      "CE", -3.733500,  -38.506100),
    ("C033", "Casa das Cuecas & Modas",   "(85) 9 9333-9090", "Wagner Sales",     "60420-010", "R. Barao de Aracati",         "810",  "Dionisio Torres", "Fortaleza",      "CE", -3.745000,  -38.502300),
]


async def semear_banco(db: AsyncSession) -> dict:
    """Cria admin + usuarios de exemplo + clientes ficticios quando as tabelas estiverem vazias."""
    criados = {"admin": 0, "usuarios": 0, "clientes": 0}

    if not SEED_DEMO:
        logger.info("[SEED] SEED_DEMO desativado — pulando carga de dados demo.")
        return criados

    total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    if total_users == 0:
        admin = User(
            email=ADMIN_EMAIL,
            name=ADMIN_NAME,
            password_hash=hash_password(ADMIN_PASSWORD),
            auth_provider="local",
            role="admin",
            empresa="AC",
            permissions=[],
            is_active=True,
        )
        db.add(admin)
        criados["admin"] = 1
        logger.info("[SEED] Admin local criado: %s", ADMIN_EMAIL)

        # Usuarios de exemplo com permissoes diferentes
        for email, name, pwd, perms, empresa in _USUARIOS_EXEMPLO:
            db.add(User(
                email=email, name=name,
                password_hash=hash_password(pwd),
                auth_provider="local", role="user",
                permissions=perms, empresa=empresa, is_active=True,
            ))
            logger.info("[SEED] User criado: %s perms: %s", email, perms)
        criados["usuarios"] = len(_USUARIOS_EXEMPLO)
    else:
        logger.info("[SEED] %d usuarios ja existem - pulando criacao de usuarios.", total_users)

    total_clientes = (await db.execute(select(func.count()).select_from(Cliente))).scalar() or 0
    if total_clientes == 0:
        agora = datetime.now(timezone.utc)
        for i, (codigo, nome, tel, contato, cep, rua, num, bairro, cidade, uf, lat, lon) in enumerate(_CLIENTES_FICTICIOS):
            c = Cliente(
                codigo=codigo,
                nome_razao_social=nome,
                telefone=tel,
                pessoa_contato=contato,
                cep=cep, rua=rua, numero=num, bairro=bairro,
                cidade=cidade, estado=uf,
                latitude=lat, longitude=lon,
                updated_at=agora,
            )
            db.add(c)
            await db.flush()
            # Endereco principal (espelho dos campos flat)
            e = ClienteEndereco(
                cliente_id=c.id, nome="Endereço principal", ordem=0,
                cep=cep, rua=rua, numero=num, bairro=bairro,
                cidade=cidade, estado=uf, latitude=lat, longitude=lon,
                created_at=agora, updated_at=agora,
            )
            db.add(e)
            await db.flush()
            # Contato principal (espelho de pessoa_contato/telefone)
            if contato or tel:
                db.add(ClienteContato(
                    endereco_id=e.id, nome=contato or "", telefone=tel or None,
                    created_at=agora,
                ))
            # Alguns clientes de exemplo ganham uma segunda loja (filial)
            if i % 5 == 0:
                filial_cep = f"{cep[:5]}-{str(i).zfill(3)}"
                db.add(ClienteEndereco(
                    cliente_id=c.id, nome="Filial (loja 2)", ordem=1,
                    cep=filial_cep, rua=f"Av. Filial {i + 1}", numero=str(100 + i),
                    bairro="Centro", cidade=cidade, estado=uf,
                    latitude=round(lat + 0.01, 8), longitude=round(lon + 0.01, 8),
                    created_at=agora, updated_at=agora,
                ))
            # Alguns enderecos ganham mais de um contato
            if i % 3 == 0:
                db.add(ClienteContato(
                    endereco_id=e.id, nome="Contato extra", telefone=tel,
                    created_at=agora,
                ))
        criados["clientes"] = len(_CLIENTES_FICTICIOS)
        logger.info("[SEED] %d clientes ficticios criados (com enderecos/contatos).", len(_CLIENTES_FICTICIOS))
    else:
        logger.info("[SEED] %d clientes ja existem - pulando carga de clientes.", total_clientes)

    await db.commit()
    return criados