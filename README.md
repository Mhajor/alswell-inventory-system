# ALSWELL Management System - AI Optimization Platform

An intelligent retail inventory management system built with **FastAPI**, **SQLAlchemy**, **MySQL**, and **OpenAI GPT-4o-mini**. 

This application handles real-time catalog management, automated order checkout workflows, dynamic stock adjustment, revenue analytics, and supply chain optimization using an embedded AI agent to calculate Economic Order Quantity (EOQ).

---

## Key Features

* **AI-Powered Supply Chain Optimization:** Leverages an OpenAI agent to analyze historical sales data and stock levels to calculate optimal Economic Order Quantities (EOQ).
* **Inventory Catalog Management:** Full RESTful CRUD capabilities for managing SKUs, prices, current stock levels, safety thresholds, and restock actions.
* **Order Processing & Workflow Engine:** Handles shopping cart checkout with automatic transaction reference generation (`ALS-XXXXXX`), stock validation, and lifecycle transitions (`Pending` $\rightarrow$ `Approved`/`Completed` or `Cancelled`).
* **Revenue Analytics:** Aggregates daily realized revenue, total platform revenue, and monthly sales breakdowns via custom database query routines.
* **Role-Based Authentication:** Endpoint architecture built to support role assignments (`Customer`, `Staff`, `Admin`).

---

## Tech Stack & Architecture

| Layer | Technology |
| :--- | :--- |
| **Framework** | FastAPI (Python 3.10+) |
| **Database ORM** | SQLAlchemy |
| **Database Engine** | MySQL (via `PyMySQL`) |
| **Data Validation** | Pydantic v2 |
| **AI Integration** | OpenAI API (`gpt-4o-mini` with Structured Outputs) |
| **Server Engine** | Uvicorn ASGI |

---

## Getting Started

### Prerequisites

Ensure you have the following installed on your machine:
* [Python 3.10+](https://www.python.org/)
* [MySQL Server](https://dev.mysql.com/downloads/mysql/) (running on port `3306`)
* [Git](https://git-scm.com/)

---

### Local Installation & Setup

1. **Clone the Repository**
   ```bash
   git clone [https://github.com/Mhajor/alswell-inventory-system.git](https://github.com/Mhajor/alswell-inventory-system.git)
   cd alswell-inventory-system
