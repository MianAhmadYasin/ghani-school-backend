from fastapi import APIRouter, HTTPException, status, Depends, Query, Response
from typing import Optional, List
from datetime import date, datetime, timedelta
from app.models.finance import (
    StationeryItemCreate, StationeryItemUpdate, StationeryItemResponse,
    StationeryDistributionCreate, StationeryDistributionResponse,
    SalaryRecordCreate, SalaryRecordUpdate, SalaryRecordResponse,
    ExpenseCreate, ExpenseUpdate, ExpenseResponse,
    DonationCreate, DonationUpdate, DonationResponse,
    InvoiceCreate, InvoiceUpdate, InvoiceResponse, InvoiceItem,
    FinancialSummary, FinancialReportRequest
)
from app.core.supabase import supabase, get_request_scoped_client
from app.core.security import get_current_user, require_role
from app.core.logging_config import get_logger
from app.core.exceptions import DatabaseError, NotFoundError, ValidationError, sanitize_error_message
from app.core.invoice_utils import (
    generate_invoice_number, calculate_due_date, build_invoice_items,
    validate_invoice_status, update_invoice_status_if_overdue
)

logger = get_logger(__name__)
router = APIRouter()


# ==================== Stationery Items ====================

@router.post("/stationery/items", response_model=StationeryItemResponse, status_code=status.HTTP_201_CREATED)
async def create_stationery_item(
    item_data: StationeryItemCreate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Create a new stationery item"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        response = db.table("stationery_items").insert(item_data.model_dump()).execute()
        logger.info(f"Stationery item created: {response.data[0].get('id')}")
        return StationeryItemResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to create stationery item: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to create stationery item: {error_message}", error_code="STATIONERY_CREATE_ERROR")


@router.get("/stationery/items", response_model=list[StationeryItemResponse])
async def list_stationery_items(
    category: Optional[str] = Query(None),
    low_stock: bool = Query(False),
    current_user: dict = Depends(get_current_user)
):
    """List all stationery items"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin","principal"]) 
        query = db.table("stationery_items").select("*")
        
        if category:
            query = query.eq("category", category)
        
        response = query.execute()
        items = [StationeryItemResponse(**item) for item in response.data]
        
        if low_stock:
            items = [item for item in items if item.quantity <= item.reorder_level]
        
        return items
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/stationery/items/{item_id}", response_model=StationeryItemResponse)
async def get_stationery_item(
    item_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific stationery item"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin","principal"])
        response = db.table("stationery_items").select("*").eq("id", item_id).execute()
        
        if not response.data:
            raise NotFoundError(f"Stationery item with ID {item_id} not found", error_code="STATIONERY_NOT_FOUND")
        
        return StationeryItemResponse(**response.data[0])
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get stationery item {item_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch stationery item: {error_message}", error_code="STATIONERY_FETCH_ERROR")


@router.put("/stationery/items/{item_id}", response_model=StationeryItemResponse)
async def update_stationery_item(
    item_id: str,
    item_data: StationeryItemUpdate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Update a stationery item"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Check if item exists
        existing = db.table("stationery_items").select("*").eq("id", item_id).execute()
        if not existing.data:
            raise NotFoundError(f"Stationery item with ID {item_id} not found", error_code="STATIONERY_NOT_FOUND")
        
        # Update only provided fields
        update_data = {k: v for k, v in item_data.model_dump().items() if v is not None}
        response = db.table("stationery_items").update(update_data).eq("id", item_id).execute()
        
        logger.info(f"Stationery item updated: {item_id}")
        return StationeryItemResponse(**response.data[0])
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update stationery item {item_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to update stationery item: {error_message}", error_code="STATIONERY_UPDATE_ERROR")


@router.delete("/stationery/items/{item_id}")
async def delete_stationery_item(
    item_id: str,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Delete a stationery item"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Check if item exists
        existing = db.table("stationery_items").select("*").eq("id", item_id).execute()
        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stationery item not found")
        
        db.table("stationery_items").delete().eq("id", item_id).execute()
        return {"message": "Stationery item deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==================== Stationery Distributions ====================

@router.post("/stationery/distributions", response_model=StationeryDistributionResponse, status_code=status.HTTP_201_CREATED)
async def distribute_stationery(
    distribution_data: StationeryDistributionCreate,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Distribute stationery to a student"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Check if student exists
        student = db.table("students").select("*").eq("id", distribution_data.student_id).execute()
        if not student.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
        
        # Check if item exists and has enough quantity
        item = db.table("stationery_items").select("*").eq("id", distribution_data.item_id).execute()
        if not item.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stationery item not found")
        
        if item.data[0]["quantity"] < distribution_data.quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient quantity")
        
        # Create distribution record
        distribution_record = distribution_data.model_dump()
        distribution_record["distributed_by"] = current_user["sub"]
        
        response = db.table("stationery_distributions").insert(distribution_record).execute()
        
        # Update item quantity
        new_quantity = item.data[0]["quantity"] - distribution_data.quantity
        db.table("stationery_items").update({"quantity": new_quantity}).eq("id", distribution_data.item_id).execute()
        
        return StationeryDistributionResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/stationery/distributions", response_model=list[StationeryDistributionResponse])
async def list_distributions(
    student_id: Optional[str] = Query(None),
    item_id: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """List stationery distributions"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin","principal"])
        query = db.table("stationery_distributions").select("*")
        
        if student_id:
            query = query.eq("student_id", student_id)
        if item_id:
            query = query.eq("item_id", item_id)
        if date_from:
            query = query.gte("distributed_date", date_from.isoformat())
        if date_to:
            query = query.lte("distributed_date", date_to.isoformat())
        
        response = query.execute()
        return [StationeryDistributionResponse(**item) for item in response.data]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==================== Salary Records ====================

@router.post("/salaries", response_model=SalaryRecordResponse, status_code=status.HTTP_201_CREATED)
async def create_salary_record(
    salary_data: SalaryRecordCreate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Create a salary record for a teacher"""
    try:
        logger.debug(f"Creating salary record: teacher_id={salary_data.teacher_id}, month={salary_data.month}, year={salary_data.year}")
        
        db = get_request_scoped_client(current_user.get("access_token"), True)
        # Calculate net salary
        net_salary = salary_data.basic_salary + salary_data.bonuses - salary_data.deductions
        
        salary_record = salary_data.model_dump()
        salary_record["net_salary"] = net_salary
        
        logger.debug(f"Calculated net salary: {net_salary}")
        
        response = db.table("salary_records").insert(salary_record).execute()
        logger.info(f"Salary record created successfully: {response.data[0].get('id')}")
        return SalaryRecordResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to create salary record: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to create salary record: {error_message}", error_code="SALARY_CREATE_ERROR")


@router.get("/salaries", response_model=list[SalaryRecordResponse])
async def list_salary_records(
    teacher_id: Optional[str] = Query(None),
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """List salary records"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin","principal"])
        query = db.table("salary_records").select("*")
        
        if teacher_id:
            query = query.eq("teacher_id", teacher_id)
        if month:
            query = query.eq("month", month)
        if year:
            query = query.eq("year", year)
        
        response = query.execute()
        return [SalaryRecordResponse(**item) for item in response.data]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/salaries/{salary_id}", response_model=SalaryRecordResponse)
async def update_salary_record(
    salary_id: str,
    salary_data: SalaryRecordUpdate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Update a salary record"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Check if salary record exists
        existing = db.table("salary_records").select("*").eq("id", salary_id).execute()
        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salary record not found")
        
        # Update only provided fields
        update_data = {k: v for k, v in salary_data.model_dump().items() if v is not None}
        
        # Recalculate net salary if basic_salary, bonuses, or deductions are updated
        if any(field in update_data for field in ["basic_salary", "bonuses", "deductions"]):
            current_data = existing.data[0]
            basic_salary = update_data.get("basic_salary", current_data["basic_salary"])
            bonuses = update_data.get("bonuses", current_data["bonuses"])
            deductions = update_data.get("deductions", current_data["deductions"])
            update_data["net_salary"] = basic_salary + bonuses - deductions
        
        response = db.table("salary_records").update(update_data).eq("id", salary_id).execute()
        logger.info(f"Salary record updated: {salary_id}")
        return SalaryRecordResponse(**response.data[0])
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update salary record {salary_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to update salary record: {error_message}", error_code="SALARY_UPDATE_ERROR")


@router.delete("/salaries/{salary_id}")
async def delete_salary_record(
    salary_id: str,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Delete a salary record"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Check if salary record exists
        existing = db.table("salary_records").select("*").eq("id", salary_id).execute()
        if not existing.data:
            raise NotFoundError(f"Salary record with ID {salary_id} not found", error_code="SALARY_NOT_FOUND")
        
        db.table("salary_records").delete().eq("id", salary_id).execute()
        logger.info(f"Salary record deleted: {salary_id}")
        return {"message": "Salary record deleted successfully"}
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to delete salary record {salary_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to delete salary record: {error_message}", error_code="SALARY_DELETE_ERROR")


# ==================== Expenses ====================

@router.post("/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    expense_data: ExpenseCreate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Record a new expense"""
    try:
        logger.debug(f"Creating expense: category={expense_data.category}, amount={expense_data.amount}")
        
        db = get_request_scoped_client(current_user.get("access_token"), True)
        expense_record = expense_data.model_dump()
        expense_record["recorded_by"] = current_user["sub"]
        
        response = db.table("expenses").insert(expense_record).execute()
        logger.info(f"Expense created successfully: {response.data[0].get('id')}")
        return ExpenseResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to create expense: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to create expense: {error_message}", error_code="EXPENSE_CREATE_ERROR")


@router.get("/expenses", response_model=list[ExpenseResponse])
async def list_expenses(
    category: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """List expenses"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin","principal"])
        query = db.table("expenses").select("*")
        
        if category:
            query = query.eq("category", category)
        if date_from:
            query = query.gte("date", date_from.isoformat())
        if date_to:
            query = query.lte("date", date_to.isoformat())
        
        response = query.execute()
        return [ExpenseResponse(**item) for item in response.data]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/expenses/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: str,
    expense_data: ExpenseUpdate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Update an expense"""
    try:
        logger.debug(f"Updating expense: id={expense_id}")
        
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Check if expense exists
        existing = db.table("expenses").select("*").eq("id", expense_id).execute()
        if not existing.data:
            raise NotFoundError(f"Expense with ID {expense_id} not found", error_code="EXPENSE_NOT_FOUND")
        
        # Update only provided fields
        update_data = {k: v for k, v in expense_data.model_dump().items() if v is not None}
        
        response = db.table("expenses").update(update_data).eq("id", expense_id).execute()
        logger.info(f"Expense updated successfully: {expense_id}")
        return ExpenseResponse(**response.data[0])
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update expense {expense_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to update expense: {error_message}", error_code="EXPENSE_UPDATE_ERROR")


@router.delete("/expenses/{expense_id}")
async def delete_expense(
    expense_id: str,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Delete an expense"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Check if expense exists
        existing = db.table("expenses").select("*").eq("id", expense_id).execute()
        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
        
        db.table("expenses").delete().eq("id", expense_id).execute()
        return {"message": "Expense deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==================== Donations ====================

@router.post("/donations", response_model=DonationResponse, status_code=status.HTTP_201_CREATED)
async def create_donation(
    donation_data: DonationCreate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Record a new donation"""
    try:
        logger.debug(f"Creating donation: donor={donation_data.donor_name}, amount={donation_data.amount}")
        
        db = get_request_scoped_client(current_user.get("access_token"), True)
        donation_record = donation_data.model_dump()
        
        response = db.table("donations").insert(donation_record).execute()
        logger.info(f"Donation created successfully: {response.data[0].get('id')}")
        return DonationResponse(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to create donation: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to create donation: {error_message}", error_code="DONATION_CREATE_ERROR")


@router.get("/donations", response_model=list[DonationResponse])
async def list_donations(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """List donations"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), current_user.get("role") in ["admin","principal"])
        query = db.table("donations").select("*")
        
        if date_from:
            query = query.gte("date", date_from.isoformat())
        if date_to:
            query = query.lte("date", date_to.isoformat())
        
        response = query.execute()
        return [DonationResponse(**item) for item in response.data]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/donations/{donation_id}", response_model=DonationResponse)
async def update_donation(
    donation_id: str,
    donation_data: DonationUpdate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Update a donation"""
    try:
        logger.debug(f"Updating donation: id={donation_id}")
        
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Check if donation exists
        existing = db.table("donations").select("*").eq("id", donation_id).execute()
        if not existing.data:
            raise NotFoundError(f"Donation with ID {donation_id} not found", error_code="DONATION_NOT_FOUND")
        
        # Update only provided fields
        update_data = {k: v for k, v in donation_data.model_dump().items() if v is not None}
        
        response = db.table("donations").update(update_data).eq("id", donation_id).execute()
        logger.info(f"Donation updated successfully: {donation_id}")
        return DonationResponse(**response.data[0])
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update donation {donation_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to update donation: {error_message}", error_code="DONATION_UPDATE_ERROR")


@router.delete("/donations/{donation_id}")
async def delete_donation(
    donation_id: str,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Delete a donation"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Check if donation exists
        existing = db.table("donations").select("*").eq("id", donation_id).execute()
        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Donation not found")
        
        db.table("donations").delete().eq("id", donation_id).execute()
        return {"message": "Donation deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==================== Invoices ====================

@router.post("/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def generate_invoice(
    invoice_data: InvoiceCreate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Generate an invoice for an approved salary calculation"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Get salary calculation
        calc_response = db.table("monthly_salary_calculations")\
            .select("*")\
            .eq("id", invoice_data.calculation_id)\
            .single()\
            .execute()
        
        if not calc_response.data:
            raise NotFoundError(
                f"Salary calculation {invoice_data.calculation_id} not found",
                error_code="CALCULATION_NOT_FOUND"
            )
        
        calculation = calc_response.data
        
        # Check if calculation is approved
        if not calculation.get("is_approved"):
            raise ValidationError(
                "Cannot generate invoice for unapproved salary calculation",
                error_code="CALCULATION_NOT_APPROVED"
            )
        
        # Check if invoice already exists for this calculation
        existing_invoice = db.table("invoices")\
            .select("*")\
            .eq("calculation_id", invoice_data.calculation_id)\
            .execute()
        
        if existing_invoice.data:
            # Return existing invoice
            logger.info(f"Invoice already exists for calculation {invoice_data.calculation_id}")
            return InvoiceResponse(**existing_invoice.data[0])
        
        teacher_id = calculation["teacher_id"]
        month = calculation["calculation_month"]
        year = calculation["calculation_year"]
        
        # Generate invoice number
        invoice_number = generate_invoice_number(db, month, year)
        
        # Set invoice date
        if invoice_data.invoice_date:
            invoice_date = datetime.fromisoformat(invoice_data.invoice_date).date()
        else:
            invoice_date = date.today()
        
        # Calculate due date
        if invoice_data.due_date:
            due_date = datetime.fromisoformat(invoice_data.due_date).date()
        else:
            due_date = calculate_due_date(invoice_date, days=30)
        
        # Build invoice items
        items = build_invoice_items(calculation, template=invoice_data.template)
        
        # Calculate totals
        subtotal = float(calculation.get("basic_salary", 0))
        deductions = float(calculation.get("total_deductions", 0))
        bonuses = float(calculation.get("bonuses", 0)) if "bonuses" in calculation else 0.0
        net_amount = float(calculation.get("net_salary", 0))
        tax = 0.0  # Tax can be added if needed
        total_amount = net_amount + tax
        
        # Create invoice record
        invoice_record = {
            "invoice_number": invoice_number,
            "teacher_id": teacher_id,
            "calculation_id": invoice_data.calculation_id,
            "month": month,
            "year": year,
            "invoice_date": invoice_date.isoformat(),
            "due_date": due_date.isoformat(),
            "status": "draft",
            "items": items,
            "subtotal": subtotal,
            "deductions": deductions,
            "bonuses": bonuses,
            "tax": tax,
            "net_amount": net_amount,
            "total_amount": total_amount,
            "notes": invoice_data.notes
        }
        
        response = db.table("invoices").insert(invoice_record).execute()
        
        if not response.data:
            raise DatabaseError("Failed to create invoice", error_code="INVOICE_CREATE_FAILED")
        
        logger.info(f"Invoice generated: {invoice_number} for teacher {teacher_id}")
        return InvoiceResponse(**response.data[0])
        
    except (NotFoundError, ValidationError, DatabaseError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to generate invoice: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to generate invoice: {error_message}", error_code="INVOICE_GENERATION_ERROR")


@router.get("/invoices", response_model=List[InvoiceResponse])
async def list_invoices(
    teacher_id: Optional[str] = Query(None),
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    calculation_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """List invoices with filtering"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        # Update overdue invoices
        update_invoice_status_if_overdue(db)
        
        query = db.table("invoices").select("*")
        
        # For teachers, only show their own invoices
        if user_role == "teacher":
            teacher_check = db.table("teachers").select("id").eq("user_id", current_user["sub"]).single().execute()
            if teacher_check.data:
                query = query.eq("teacher_id", teacher_check.data["id"])
            else:
                return []  # Teacher record not found
        
        if teacher_id:
            query = query.eq("teacher_id", teacher_id)
        if month:
            query = query.eq("month", month)
        if year:
            query = query.eq("year", year)
        if status:
            if not validate_invoice_status(status):
                raise ValidationError(f"Invalid invoice status: {status}", error_code="INVALID_STATUS")
            query = query.eq("status", status)
        if calculation_id:
            query = query.eq("calculation_id", calculation_id)
        
        response = query.order("created_at", desc=True).execute()
        return [InvoiceResponse(**inv) for inv in response.data]
        
    except ValidationError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch invoices: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch invoices: {error_message}", error_code="INVOICE_FETCH_ERROR")


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get invoice by ID"""
    try:
        user_role = current_user.get("role")
        is_admin = user_role in ["admin", "principal"]
        db = get_request_scoped_client(
            current_user.get("access_token"),
            is_admin,
            current_user.get("supabase_token")
        )
        
        response = db.table("invoices").select("*").eq("id", invoice_id).single().execute()
        
        if not response.data:
            raise NotFoundError(f"Invoice {invoice_id} not found", error_code="INVOICE_NOT_FOUND")
        
        invoice = response.data
        
        # For teachers, verify they can access this invoice
        if user_role == "teacher":
            teacher_check = db.table("teachers").select("id").eq("user_id", current_user["sub"]).single().execute()
            if teacher_check.data:
                if invoice.get("teacher_id") != teacher_check.data["id"]:
                    raise NotFoundError("Invoice not found", error_code="INVOICE_NOT_FOUND")
        
        return InvoiceResponse(**invoice)
        
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch invoice {invoice_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to fetch invoice: {error_message}", error_code="INVOICE_FETCH_ERROR")


@router.put("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: str,
    invoice_data: InvoiceUpdate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Update invoice (status, due_date, notes)"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Check if invoice exists
        existing = db.table("invoices").select("*").eq("id", invoice_id).single().execute()
        if not existing.data:
            raise NotFoundError(f"Invoice {invoice_id} not found", error_code="INVOICE_NOT_FOUND")
        
        update_data = invoice_data.model_dump(exclude_unset=True)
        
        # Validate status if provided
        if "status" in update_data:
            if not validate_invoice_status(update_data["status"]):
                raise ValidationError(f"Invalid invoice status: {update_data['status']}", error_code="INVALID_STATUS")
        
        response = db.table("invoices").update(update_data).eq("id", invoice_id).execute()
        
        if not response.data:
            raise DatabaseError("Failed to update invoice", error_code="INVOICE_UPDATE_FAILED")
        
        logger.info(f"Invoice updated: {invoice_id}")
        return InvoiceResponse(**response.data[0])
        
    except (NotFoundError, ValidationError, DatabaseError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update invoice {invoice_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to update invoice: {error_message}", error_code="INVOICE_UPDATE_ERROR")


@router.get("/invoices/{invoice_id}/download")
async def download_invoice(
    invoice_id: str,
    format: str = Query("pdf", regex="^(pdf|html)$"),
    current_user: dict = Depends(get_current_user)
):
    """Download invoice as PDF or HTML"""
    try:
        db = get_request_scoped_client(current_user.get("access_token"), True)
        
        # Get invoice
        response = db.table("invoices").select("*").eq("id", invoice_id).single().execute()
        if not response.data:
            raise NotFoundError(f"Invoice {invoice_id} not found", error_code="INVOICE_NOT_FOUND")
        
        invoice = response.data
        
        # For now, return JSON response. PDF/HTML generation will be added with PDF generator
        # TODO: Implement PDF/HTML generation using report_generator
        if format == "html":
            # Generate HTML invoice
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Invoice {invoice['invoice_number']}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .header {{ text-align: center; margin-bottom: 30px; }}
                    .invoice-details {{ margin-bottom: 20px; }}
                    table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                    .total {{ font-weight: bold; }}
                    .footer {{ margin-top: 30px; text-align: center; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>INVOICE</h1>
                    <p>Invoice Number: {invoice['invoice_number']}</p>
                </div>
                <div class="invoice-details">
                    <p>Date: {invoice['invoice_date']}</p>
                    <p>Due Date: {invoice.get('due_date', 'N/A')}</p>
                    <p>Status: {invoice['status']}</p>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Description</th>
                            <th>Quantity</th>
                            <th>Unit Price</th>
                            <th>Amount</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for item in invoice.get("items", []):
                html_content += f"""
                        <tr>
                            <td>{item.get('description', '')}</td>
                            <td>{item.get('quantity', 1)}</td>
                            <td>${item.get('unit_price', 0):.2f}</td>
                            <td>${item.get('amount', 0):.2f}</td>
                        </tr>
                """
            
            html_content += f"""
                    </tbody>
                </table>
                <div class="total">
                    <p>Subtotal: ${invoice['subtotal']:.2f}</p>
                    <p>Deductions: ${invoice['deductions']:.2f}</p>
                    <p>Bonuses: ${invoice['bonuses']:.2f}</p>
                    <p>Tax: ${invoice['tax']:.2f}</p>
                    <p><strong>Total: ${invoice['total_amount']:.2f}</strong></p>
                </div>
                {f"<div class='footer'><p>Notes: {invoice.get('notes', '')}</p></div>" if invoice.get('notes') else ''}
            </body>
            </html>
            """
            
            return Response(content=html_content, media_type="text/html")
        
        # Return JSON for now (PDF generation will be added later)
        return {"invoice": invoice, "format": format}
        
    except NotFoundError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to download invoice {invoice_id}: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to download invoice: {error_message}", error_code="INVOICE_DOWNLOAD_ERROR")


# ==================== Financial Reports ====================

@router.get("/reports/summary", response_model=FinancialSummary)
async def get_financial_summary(
    report_type: str = Query("monthly", regex="^(daily|weekly|monthly|6-month|yearly|custom)$"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    include_comparison: bool = Query(True),
    current_user: dict = Depends(get_current_user)
):
    """Get financial summary for a period"""
    try:
        from app.core.financial_reporting import FinancialReportGenerator
        
        db = get_request_scoped_client(current_user.get("access_token"), True)
        generator = FinancialReportGenerator(db)
        
        report = generator.generate_report(
            report_type=report_type,
            date_from=date_from,
            date_to=date_to,
            include_comparison=include_comparison
        )
        
        return FinancialSummary(**report)
        
    except ValueError as e:
        raise ValidationError(str(e), error_code="INVALID_REPORT_PARAMS")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to generate financial summary: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to generate financial summary: {error_message}", error_code="REPORT_GENERATION_ERROR")


@router.post("/reports", response_model=FinancialSummary)
async def generate_financial_report(
    report_request: FinancialReportRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate financial report with custom parameters"""
    try:
        from app.core.financial_reporting import FinancialReportGenerator
        
        db = get_request_scoped_client(current_user.get("access_token"), True)
        generator = FinancialReportGenerator(db)
        
        report = generator.generate_report(
            report_type=report_request.report_type,
            date_from=report_request.date_from,
            date_to=report_request.date_to,
            include_comparison=True
        )
        
        # TODO: Handle format parameter (pdf, excel, csv) when PDF generator is implemented
        # For now, return JSON
        
        return FinancialSummary(**report)
        
    except ValueError as e:
        raise ValidationError(str(e), error_code="INVALID_REPORT_PARAMS")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to generate financial report: {str(e)}")
        error_message = sanitize_error_message(e)
        raise DatabaseError(f"Failed to generate financial report: {error_message}", error_code="REPORT_GENERATION_ERROR")