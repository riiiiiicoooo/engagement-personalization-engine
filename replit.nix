{ pkgs }: {
  deps = [
    pkgs.nodejs_20
    pkgs.postgresql
    pkgs.redis
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.git
    pkgs.curl
  ];

  env = {
    POSTGRESQL_URL = "postgresql://user:password@localhost/engagement_engine";
    REDIS_URL = "redis://localhost:6379";
  };
}
