// Memory Vault Portal config.
// NOTE: anon key is safe to publish; RLS policies enforce consumer_uid isolation.
// Service key NEVER goes here.
window.AIMG_CONFIG = {
  supabaseUrl: 'REPLACED_AT_DEPLOY_TIME',
  supabaseAnonKey: 'REPLACED_AT_DEPLOY_TIME',
  schema: 'public',
  memoriesTable: 'consumer_memories',
  einsteinChecksTable: 'einstein_checks',
  deployedAt: 'REPLACED_AT_DEPLOY_TIME',
};
