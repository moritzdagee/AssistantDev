/**
 * Zentrale Endpunkt-Referenz — alle Pfade die das Python-Backend
 * (src/web_server.py) bereitstellt. Wird von den Pages/Components
 * ueber `api.get(endpoints.agents)` etc. verwendet, damit die
 * Endpunkt-Strings nicht ueber das Projekt verstreut sind.
 *
 * Falls ein Endpunkt hier fehlt: im Backend nachschlagen
 * (Grep nach `self.path ==` oder `path.startswith(` in
 * src/web_server.py) und hier ergaenzen.
 */
export const endpoints = {
  agents: '/agents',
  models: '/models',
  send: '/send',
  chat: '/chat',
  messages: '/messages',
  conversations: '/conversations',
  search: '/search',
  downloadFile: '/download_file',
  uploadFile: '/upload_file',
  memory: '/memory',
  workingMemory: '/working_memory',
  capabilities: '/capabilities',
  permissions: '/permissions',
  slack: '/slack',
  canva: '/canva',
  calendar: '/calendar',
  changelog: '/changelog',
  docs: '/docs',
} as const;

export type EndpointKey = keyof typeof endpoints;
