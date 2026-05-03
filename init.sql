-- Create application user if not exists
-- This runs on first MySQL container start (docker-entrypoint-initdb.d)

CREATE USER IF NOT EXISTS 'stock_user'@'%' IDENTIFIED WITH mysql_native_password BY 'changeme';
GRANT ALL PRIVILEGES ON stock_cursor.* TO 'stock_user'@'%';
FLUSH PRIVILEGES;
