USE shop_max;

INSERT IGNORE INTO categories (id, name) VALUES
(1, 'Men'),
(2, 'Women'),
(3, 'Footwear'),
(4, 'Accessories');

INSERT IGNORE INTO users (id, name, email, password_hash, is_admin) VALUES
(1, 'Admin User', 'admin@shopmax.com', 'pbkdf2:sha1:600000$shopmaxsalt$c8032c41c8cc9ebbddd44ee7610cdcd8777ee725eee7dd5e64c28ca75313ec0a', 1);

INSERT IGNORE INTO products (id, name, brand, description, price, stock, category_id, image_url, is_active) VALUES
(1, 'Classic Denim Jacket', 'Urban Peak', 'Slim fit denim jacket with stretch comfort.', 2499.00, 50, 1, 'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab', 1),
(2, 'Floral Summer Dress', 'Luxe Bloom', 'Lightweight floral dress perfect for brunch and travel.', 1899.00, 35, 2, 'https://images.unsplash.com/photo-1496747611176-843222e1e57c', 1),
(3, 'Street Runner Sneakers', 'StrideX', 'Cushioned running sneakers with breathable mesh.', 2999.00, 70, 3, 'https://images.unsplash.com/photo-1542291026-7eec264c27ff', 1),
(4, 'Minimal Leather Belt', 'Craft & Co', 'Premium textured leather belt with matte buckle.', 899.00, 90, 4, 'https://images.unsplash.com/photo-1588361861040-ac9b1018f6d5', 1),
(5, 'Oversized Hoodie', 'North Thread', 'Soft cotton fleece hoodie with ribbed cuffs.', 1599.00, 60, 1, 'https://images.unsplash.com/photo-1556821840-3a63f95609a7', 1),
(6, 'Canvas Tote Bag', 'Urban Carry', 'Daily utility tote with inside zip pocket.', 1199.00, 45, 4, 'https://images.unsplash.com/photo-1591561954557-26941169b49e', 1),
(7, 'Heeled Sandals', 'Velvet Walk', 'Comfort-fit heeled sandals with anti-slip sole.', 2199.00, 30, 3, 'https://images.unsplash.com/photo-1543163521-1bf539c55dd2', 1),
(8, 'Pleated Midi Skirt', 'Aura Line', 'Flowy midi skirt with modern pleat detailing.', 1699.00, 40, 2, 'https://images.unsplash.com/photo-1583496661160-fb5886a13d26', 1);