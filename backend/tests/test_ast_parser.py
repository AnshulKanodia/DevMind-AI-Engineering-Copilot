from app.schemas.ast_nodes import CodeSymbolType
from app.services.ast_parser import ast_parser_service


PYTHON_SAMPLE = '''"""Module docstring."""

class UserService:
    """Service to handle user registration."""

    def __init__(self, db_client):
        self.db = db_client

    async def register_user(self, email: str) -> bool:
        """Register a new user in the database."""
        return True

def standalone_helper(x: int) -> int:
    return x * 2
'''

TYPESCRIPT_SAMPLE = '''export interface UserProfile {
    id: string;
    email: string;
}

export class AuthManager {
    private secret: string;

    constructor(secret: string) {
        this.secret = secret;
    }
}

export async function verifyToken(token: string): Promise<boolean> {
    return token.length > 0;
}

export const generateSalt = () => {
    return "salt";
};
'''

GO_SAMPLE = '''package main

type ServerConfig struct {
    Port int
    Host string
}

func (s *ServerConfig) GetAddress() string {
    return s.Host
}

func StartServer(port int) error {
    return nil
}
'''


def test_python_ast_parsing():
    ast_res = ast_parser_service.parse_file("services/user.py", PYTHON_SAMPLE)

    assert ast_res.language == "python"
    assert ast_res.total_symbols >= 4

    names = {s.name for s in ast_res.symbols}
    assert "UserService" in names
    assert "UserService.__init__" in names
    assert "UserService.register_user" in names
    assert "standalone_helper" in names

    # Check method parent mapping
    reg_method = next(s for s in ast_res.symbols if s.name == "UserService.register_user")
    assert reg_method.parent_symbol == "UserService"
    assert reg_method.symbol_type == CodeSymbolType.ASYNC_FUNCTION
    assert reg_method.docstring == "Register a new user in the database."
    assert reg_method.start_line > 0
    assert reg_method.end_line >= reg_method.start_line


def test_typescript_ast_parsing():
    ast_res = ast_parser_service.parse_file("lib/auth.ts", TYPESCRIPT_SAMPLE)

    assert ast_res.language == "typescript"
    names = {s.name for s in ast_res.symbols}

    assert "UserProfile" in names
    assert "AuthManager" in names
    assert "verifyToken" in names
    assert "generateSalt" in names

    iface = next(s for s in ast_res.symbols if s.name == "UserProfile")
    assert iface.symbol_type == CodeSymbolType.INTERFACE

    arrow_fn = next(s for s in ast_res.symbols if s.name == "generateSalt")
    assert arrow_fn.symbol_type in (CodeSymbolType.FUNCTION, CodeSymbolType.ASYNC_FUNCTION)


def test_go_ast_parsing():
    ast_res = ast_parser_service.parse_file("main.go", GO_SAMPLE)

    assert ast_res.language == "go"
    names = {s.name for s in ast_res.symbols}

    assert "ServerConfig" in names
    assert "GetAddress" in names
    assert "StartServer" in names

    method = next(s for s in ast_res.symbols if s.name == "GetAddress")
    assert method.symbol_type == CodeSymbolType.METHOD


def test_fallback_generic_parsing():
    shell_script = "echo 'starting build'\nnpm run build\necho 'done'\n"
    ast_res = ast_parser_service.parse_file("build.sh", shell_script)

    assert ast_res.total_symbols >= 1
    assert ast_res.symbols[0].symbol_type == CodeSymbolType.BLOCK
