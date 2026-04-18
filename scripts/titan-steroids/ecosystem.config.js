// PM2 ecosystem — Titan Steroids C1 MVP
// Start: pm2 start ecosystem.config.js
// Stop:  pm2 stop ecosystem.config.js
// Logs:  pm2 logs titan-steroids-scheduler
//
// Env is sourced from /etc/amg/{redis-shared,supabase}.env + /root/.titan-env
// via systemd-style EnvironmentFile — PM2 doesn't natively read these, so the
// wrapper shell script `bin/titan-steroids-start.sh` sources them before spawn.

module.exports = {
  apps: [
    {
      name: 'titan-steroids-scheduler',
      script: 'scheduler.js',
      cwd: '/opt/titan-steroids',
      instances: 1,              // MVP: single scheduler + in-proc worker
      exec_mode: 'fork',
      watch: false,
      max_memory_restart: '400M',
      restart_delay: 5000,
      env: {
        NODE_ENV: 'production',
        TITAN_STEROIDS_POLL_MS: '60000',
      },
      error_file: '/var/log/titan-steroids/error.log',
      out_file: '/var/log/titan-steroids/out.log',
      merge_logs: true,
      time: true,
    },
  ],
};
