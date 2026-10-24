import client from './client'

export async function login(email: string, password: string) {
  await client.post('/auth/login', new URLSearchParams({ username: email, password }))
}

export async function register(full_name: string, email: string, password: string) {
  await client.post('/auth/register', { full_name, email, password })
}

export async function logout() {
  await client.post('/auth/logout')
}
