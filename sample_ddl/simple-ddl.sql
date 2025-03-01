CREATE TABLE Customers (
    customer_id INT PRIMARY KEY,
    name VARCHAR,
    email VARCHAR,
    address VARCHAR
);

CREATE TABLE Products (
    product_id INT PRIMARY KEY,
    name VARCHAR,
    price DECIMAL
);

CREATE TABLE Orders (
    order_id INT PRIMARY KEY,
    order_date DATE,
    customer_id INT,
    FOREIGN KEY (customer_id) REFERENCES Customers(customer_id)
);

CREATE TABLE OrderItems (
    order_item_id INT PRIMARY KEY,
    order_id INT,
    product_id INT,
    quantity INT,
    unit_price DECIMAL,
    FOREIGN KEY (order_id) REFERENCES Orders(order_id),
    FOREIGN KEY (product_id) REFERENCES Products(product_id)
);
CREATE TABLE Categories (
    CategoryID INT PRIMARY KEY,
    Name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE ProductCategories (
    ProductID INT REFERENCES Products(ProductID),
    CategoryID INT REFERENCES Categories(CategoryID),
    PRIMARY KEY (ProductID, CategoryID)
);
