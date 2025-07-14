# server/utils/role_mapper.py
from server.schemas import Role
from server.constants.access_levels import READ, WRITE, ADMIN

ROLE_TO_ACCESS = {
    Role.VIEWER: READ,
    Role.EDITOR: WRITE,
    Role.ADMIN: ADMIN
}
