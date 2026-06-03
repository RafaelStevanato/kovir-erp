export const ACTIVE_USER_ID = "user_demo_kovir"
export const ACTIVE_USER_NAME = "Operador teste Kovir"
export const ACTIVE_USER_ROLE = "Caixa / Vendas"

export function getActiveUser() {
  return {
    id: ACTIVE_USER_ID,
    name: ACTIVE_USER_NAME,
    role: ACTIVE_USER_ROLE,
  }
}
