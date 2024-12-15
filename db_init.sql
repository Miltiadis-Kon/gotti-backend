USE gotti;

DROP table orders;

CREATE TABLE orders (
    order_id VARCHAR(255),
    client_order_id VARCHAR(255),
    created_at TIMESTAMP,
    submitted_at TIMESTAMP,
    symbol VARCHAR(50),
    qty DECIMAL(10, 2),
    filled_avg_price DECIMAL(10, 2),
    type VARCHAR(50),
    side VARCHAR(50),
    limit_price DECIMAL(10, 2),
    stop_price DECIMAL(10, 2),
    status VARCHAR(50),
    trail_percent DECIMAL(5, 2),
    trail_price DECIMAL(10, 2),
    strategy VARCHAR(50),
    stop_price_id VARCHAR(50),
    limit_price_id VARCHAR(50),
);