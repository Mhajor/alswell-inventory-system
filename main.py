import os
import uuid
import math
import json
from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, EmailStr, ConfigDict, field_serializer, Field
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Numeric, ForeignKey, Text, DateTime, func
from sqlalchemy.orm import sessionmaker, Session, relationship, declarative_base, joinedload
from openai import OpenAI
from dotenv import load_dotenv

# ==========================================
# 0. LOAD ENVIRONMENT VARIABLES
# ==========================================
load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "mysql+pymysql://root:root1234@localhost:3306/alswell_retail_inventory"
)
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

# ==========================================
# 1. DATABASE & SYSTEM INITIALIZATION
# ==========================================
connect_args = {}
if "aivencloud.com" in DATABASE_URL or "ssl" in DATABASE_URL.lower():
    connect_args = {"ssl": {"ssl_mode": "REQUIRED"}}

engine = create_engine(
    DATABASE_URL, 
    connect_args=connect_args,
    pool_size=10, 
    max_overflow=20, 
    pool_recycle=1800, 
    pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

ai_client = OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None

app = FastAPI(title="ALSWELL Management System - AI Optimization Platform")

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status": "Error"}
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# 2. RELATIONAL DATA MODEL SCHEMAS
# ==========================================
class UserModel(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(150), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    role = Column(String(50), default="Customer", nullable=False)

class ProductModel(Base):
    __tablename__ = "products"
    product_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sku = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    cost_price = Column(Numeric(10, 2), default=0.00, nullable=False)
    current_stock = Column(Integer, default=0, nullable=False)
    safety_stock_threshold = Column(Integer, default=10, nullable=False)
    economic_order_quantity = Column(Integer, default=10, nullable=False)

class OrderModel(Base):
    __tablename__ = "orders"
    order_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    customer_email = Column(String(150), nullable=False)
    customer_phone = Column(String(20), nullable=False)
    delivery_type = Column(String(50), nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    transaction_reference = Column(String(50), unique=True, nullable=False, index=True)
    order_status = Column(String(50), default="Pending", nullable=False)
    payment_status = Column(String(50), default="Paid", nullable=False)
    approved_by = Column(String(255), nullable=True)
    order_date = Column(DateTime, server_default=func.now(), nullable=False)
    
    items = relationship("OrderItemModel", back_populates="order", cascade="all, delete-orphan")

class OrderItemModel(Base):
    __tablename__ = "order_items"
    item_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    
    order = relationship("OrderModel", back_populates="items")
    product = relationship("ProductModel")

Base.metadata.create_all(bind=engine)

# ==========================================
# 3. PYDANTIC VALIDATION INTERFACES
# ==========================================
class UserRegisterPayload(BaseModel):
    email: EmailStr
    password: str
    role: Optional[str] = "Customer"

class UserResponse(BaseModel):
    email: str
    role: str
    status: str

class LoginPayload(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    email: str
    role: str
    status: str

class ProductCreate(BaseModel):
    sku: str
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    price: float
    cost_price: Optional[float] = 0.0
    current_stock: int
    safety_stock_threshold: Optional[int] = 10
    economic_order_quantity: Optional[int] = 10

class ProductUpdate(BaseModel):
    name: str
    price: float
    cost_price: Optional[float] = None
    image_url: Optional[str] = None

class RestockPayload(BaseModel):
    product_id: int = Field(..., alias="product_id")
    quantity: int

    model_config = ConfigDict(populate_by_name=True)

class ProductResponse(BaseModel):
    product_id: int
    sku: str
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    price: float
    cost_price: Optional[float] = 0.0
    current_stock: int
    safety_stock_threshold: int
    economic_order_quantity: int
    
    model_config = ConfigDict(from_attributes=True)

class CartItemPayload(BaseModel):
    product_id: int
    quantity: int

class CheckoutPayload(BaseModel):
    email: EmailStr
    phone: str
    delivery_type: str
    items: List[CartItemPayload]

class StatusUpdatePayload(BaseModel):
    status: str
    staff_email: str

class OrderItemResponse(BaseModel):
    item_id: int
    order_id: int
    product_id: int
    quantity: int
    unit_price: float

    model_config = ConfigDict(from_attributes=True)

class OrderResponse(BaseModel):
    order_id: int
    customer_email: str
    customer_phone: str
    delivery_type: str
    total_amount: float
    transaction_reference: str
    order_status: str
    payment_status: str
    approved_by: Optional[str] = None
    order_date: datetime
    items: List[OrderItemResponse] = []

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('order_date')
    def serialize_dt(self, dt: datetime, _info):
        return dt.strftime('%d/%m/%Y, %I:%M:%S %p')

class MonthlyRevenueItem(BaseModel):
    key: str
    month: str
    revenue: float

class RevenueSummaryResponse(BaseModel):
    daily_realized_revenue: float
    total_aggregate_revenue: float
    total_asset_value: float
    monthly_breakdown: List[MonthlyRevenueItem]

class EOQRecommendation(BaseModel):
    product_id: int
    recommended_eoq: int
    reasoning: str

class OptimizationResponse(BaseModel):
    recommendations: List[EOQRecommendation]

# ==========================================
# 4. SECURITY & AUTHENTICATION ENDPOINTS
# ==========================================
@app.post("/api/register", response_model=UserResponse)
def register_system_user(payload: UserRegisterPayload, db: Session = Depends(get_db)):
    existing_user = db.query(UserModel).filter(UserModel.email == payload.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="This email address is already registered.")
    
    new_user = UserModel(
        email=payload.email,
        password=payload.password,
        role=payload.role if payload.role in ["Customer", "Staff", "Admin"] else "Customer"
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"email": new_user.email, "role": new_user.role, "status": "Account Created Successfully"}

@app.post("/api/login", response_model=LoginResponse)
def login_system_user(payload: LoginPayload, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email address.")
    if user.password != payload.password:
        raise HTTPException(status_code=401, detail="Incorrect password.")
    return {
        "access_token": user.email,
        "token_type": "bearer",
        "email": user.email,
        "role": user.role,
        "status": "Authenticated Successfully"
    }

# ==========================================
# 5. REST ENGINE PRODUCT CATALOG & WORKFLOW ROUTES
# ==========================================
@app.get("/api/products", response_model=List[ProductResponse])
def get_all_products(db: Session = Depends(get_db)):
    return db.query(ProductModel).all()

@app.post("/api/products", response_model=ProductResponse)
def create_new_product(payload: ProductCreate, db: Session = Depends(get_db)):
    existing = db.query(ProductModel).filter(ProductModel.sku == payload.sku).first()
    if existing:
        raise HTTPException(status_code=400, detail="Product item with this SKU already configured.")
    
    new_prod = ProductModel(
        sku=payload.sku, 
        name=payload.name, 
        description=payload.description,
        image_url=payload.image_url,
        price=payload.price, 
        cost_price=payload.cost_price or payload.price,
        current_stock=payload.current_stock,
        safety_stock_threshold=payload.safety_stock_threshold, 
        economic_order_quantity=payload.economic_order_quantity or 10
    )
    db.add(new_prod)
    db.commit()
    db.refresh(new_prod)
    return new_prod

@app.put("/api/products/{product_id}", response_model=ProductResponse)
def update_product_catalog(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db)):
    product = db.query(ProductModel).filter(ProductModel.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Target product not found.")
    product.name = payload.name
    product.price = payload.price
    if payload.cost_price is not None:
        product.cost_price = payload.cost_price
    product.image_url = payload.image_url
    db.commit()
    db.refresh(product)
    return product

@app.post("/api/restock", response_model=ProductResponse)
def restock_product(payload: RestockPayload, db: Session = Depends(get_db)):
    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="Restock quantity must be greater than zero.")
    
    product = db.query(ProductModel).filter(ProductModel.product_id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Target product not found.")
    
    product.current_stock = (product.current_stock or 0) + payload.quantity
    db.commit()
    db.refresh(product)
    return product

@app.delete("/api/products/{product_id}")
def purge_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(ProductModel).filter(ProductModel.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Target item parameters not located.")
    db.delete(product)
    db.commit()
    return {"status": "Success", "detail": "Product entity dropped safely."}

@app.get("/api/revenue-summary", response_model=RevenueSummaryResponse)
def get_revenue_summary(db: Session = Depends(get_db)):
    today_start = datetime.combine(date.today(), datetime.min.time())
    valid_statuses = ["Completed", "Approved", "Paid"]
    
    daily_rev = db.query(func.coalesce(func.sum(OrderModel.total_amount), 0)).filter(
        OrderModel.order_status.in_(valid_statuses),
        OrderModel.order_date >= today_start
    ).scalar()

    total_rev = db.query(func.coalesce(func.sum(OrderModel.total_amount), 0)).filter(
        OrderModel.order_status.in_(valid_statuses)
    ).scalar()

    asset_val = db.query(
        func.coalesce(func.sum(ProductModel.current_stock * ProductModel.cost_price), 0)
    ).scalar()

    monthly_query = db.query(
        func.date_format(OrderModel.order_date, '%Y-%m').label('month_key'),
        func.date_format(OrderModel.order_date, '%M %Y').label('month_label'),
        func.sum(OrderModel.total_amount).label('monthly_total')
    ).filter(
        OrderModel.order_status.in_(valid_statuses)
    ).group_by(
        'month_key', 'month_label'
    ).order_by(
        func.date_format(OrderModel.order_date, '%Y-%m').desc()
    ).all()

    monthly_breakdown = [
        {"key": row.month_key, "month": row.month_label, "revenue": float(row.monthly_total)}
        for row in monthly_query
    ]

    return {
        "daily_realized_revenue": float(daily_rev),
        "total_aggregate_revenue": float(total_rev),
        "total_asset_value": float(asset_val),
        "monthly_breakdown": monthly_breakdown
    }

@app.post("/api/run-ai-optimization")
def run_ai_optimization_engine(db: Session = Depends(get_db)):
    if not ai_client:
        raise HTTPException(status_code=500, detail="OpenAI API Key not configured.")
    try:
        products = db.query(ProductModel).all()
        if not products:
            return {"status": "Success", "detail": "Data registers structural inventory zeroed out."}

        inventory_data = []
        for product in products:
            historical_orders = db.query(
                OrderItemModel.quantity, OrderModel.order_date
            ).join(OrderModel).filter(
                OrderItemModel.product_id == product.product_id,
                OrderModel.order_status.in_(["Completed", "Approved"])
            ).all()

            sales_history = [
                {"quantity": item[0], "date": item[1].strftime("%Y-%m-%d")} 
                for item in historical_orders
            ]

            inventory_data.append({
                "product_id": product.product_id,
                "sku": product.sku,
                "name": product.name,
                "price": float(product.price),
                "current_stock": product.current_stock,
                "safety_stock_threshold": product.safety_stock_threshold,
                "historical_sales": sales_history
            })

        prompt = f"""
        You are an AI Supply Chain Optimization Agent.
        Analyze the following catalog, current stock, and historical sales trends:
        {json.dumps(inventory_data)}

        For each product, determine the optimal Economic Order Quantity (EOQ).
        Consider sales volume, inventory risk, and realistic minimum reorder quantities (never below 5 units).
        """

        response = ai_client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a supply chain optimization system that calculates EOQ based on sales history."},
                {"role": "user", "content": prompt}
            ],
            response_format=OptimizationResponse,
        )

        ai_results = response.choices[0].message.parsed

        for rec in ai_results.recommendations:
            prod = db.query(ProductModel).filter(ProductModel.product_id == rec.product_id).first()
            if prod:
                prod.economic_order_quantity = rec.recommended_eoq

        db.commit()
        return {
            "status": "Success", 
            "detail": "AI Agent optimization completed successfully.",
            "insights": [rec.model_dump() for rec in ai_results.recommendations]
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"AI Agent execution error: {str(e)}")

@app.get("/api/orders", response_model=List[OrderResponse])
def retrieve_system_orders(db: Session = Depends(get_db)):
    return db.query(OrderModel).options(
        joinedload(OrderModel.items).joinedload(OrderItemModel.product)
    ).order_by(OrderModel.order_id.desc()).all()

@app.post("/api/checkout")
def process_checkout(payload: CheckoutPayload, db: Session = Depends(get_db)):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Cart items cannot be empty.")

    calculated_grand_total = 0.0
    items_to_process = []

    for item in payload.items:
        product = db.query(ProductModel).filter(ProductModel.product_id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product item ID {item.product_id} no longer exists.")
        
        available_stock = product.current_stock if product.current_stock is not None else 0
        if available_stock < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient inventory reserve for '{product.name}'.")

        unit_price = float(product.price)
        calculated_grand_total += unit_price * item.quantity
        items_to_process.append((product, item.quantity, unit_price))

    generated_ref = f"ALS-{uuid.uuid4().hex[:8].upper()}"

    new_order = OrderModel(
        customer_email=payload.email,
        customer_phone=payload.phone,
        delivery_type=payload.delivery_type,
        total_amount=calculated_grand_total,
        transaction_reference=generated_ref,
        order_status="Pending",
        payment_status="Paid",
        approved_by=None
    )
    db.add(new_order)
    db.flush()

    for product, quantity, unit_price in items_to_process:
        order_item = OrderItemModel(
            order_id=new_order.order_id,
            product_id=product.product_id,
            quantity=quantity,
            unit_price=unit_price
        )
        db.add(order_item)

    db.commit()
    db.refresh(new_order)

    return {
        "status": "Success", 
        "transaction_reference": generated_ref,
        "order_id": new_order.order_id
    }

@app.put("/api/orders/{order_id}/status", response_model=OrderResponse)
@app.patch("/api/orders/{order_id}/status", response_model=OrderResponse)
def update_order_workflow_status(order_id: int, payload: StatusUpdatePayload, db: Session = Depends(get_db)):
    order = db.query(OrderModel).options(
        joinedload(OrderModel.items)
    ).filter(OrderModel.order_id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Target order matching parameters not logged.")
    
    raw_status = payload.status.strip().lower() if payload.status else ""
    status_map = {
        "complete": "Completed",
        "completed": "Completed",
        "approve": "Approved",
        "approved": "Approved",
        "cancel": "Cancelled",
        "cancelled": "Cancelled",
        "pending": "Pending"
    }

    if raw_status not in status_map:
        raise HTTPException(status_code=400, detail=f"Invalid status '{payload.status}' requested.")

    target_status = status_map[raw_status]

    try:
        if target_status in ["Approved", "Completed"] and order.order_status not in ["Approved", "Completed"]:
            for item in order.items:
                product = db.query(ProductModel).filter(ProductModel.product_id == item.product_id).first()
                if product:
                    available = product.current_stock if product.current_stock is not None else 0
                    if available < item.quantity:
                        raise HTTPException(
                            status_code=400, 
                            detail=f"Inventory failure. Insufficient levels for {product.name}. Required: {item.quantity}, Available: {available}"
                        )
                    product.current_stock = available - item.quantity

        elif target_status == "Cancelled" and order.order_status in ["Approved", "Completed"]:
            for item in order.items:
                product = db.query(ProductModel).filter(ProductModel.product_id == item.product_id).first()
                if product:
                    available = product.current_stock if product.current_stock is not None else 0
                    product.current_stock = available + item.quantity

        order.order_status = target_status
        order.approved_by = payload.staff_email[:255] if payload.staff_email else None
        
        db.commit()
        db.refresh(order)
        return order
    except HTTPException as http_exc:
        db.rollback()
        raise http_exc
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Status transition execution failure: {str(e)}")

# ==========================================
# 6. STATIC FILE MOUNTING & SERVING
# ==========================================
@app.get("/")
def read_root():
    if os.path.exists("storefront.html"):
        return FileResponse("storefront.html")
    return {"system": "ALSWELL Management System", "status": "Online"}

@app.get("/{filename}.html")
def serve_html_file(filename: str):
    filepath = f"{filename}.html"
    if os.path.exists(filepath):
        return FileResponse(filepath)
    raise HTTPException(status_code=404, detail="Requested file not found.")

app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)