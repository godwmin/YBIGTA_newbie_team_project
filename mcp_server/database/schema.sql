CREATE DATABASE IF NOT EXISTS crypto_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE crypto_db;

CREATE TABLE IF NOT EXISTS coin_prices (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    symbol VARCHAR(20) NOT NULL,
    price DECIMAL(18, 4) NOT NULL,
    change_rate FLOAT NOT NULL,
    collected_at DATETIME(6) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    INDEX idx_coin_prices_symbol_collected_at (symbol, collected_at DESC),
    INDEX idx_coin_prices_collected_at (collected_at DESC),
    CONSTRAINT chk_coin_prices_price_positive CHECK (price >= 0)
) ENGINE=InnoDB;
