"""
Stationery API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from decimal import Decimal

from app.core.supabase import supabase_admin, get_request_scoped_client
from app.core.security import get_current_user, require_role
from app.models.stationery import (
    StationeryItemCreate, StationeryItemUpdate, StationeryItemResponse,
    StationeryDistributionCreate, StationeryDistributionUpdate, StationeryDistributionResponse
)

router = APIRouter()

# Stationery Items endpoints
@router.get("/items", response_model=List[StationeryItemResponse])
async def list_stationery_items(
    category: Optional[str] = Query(None),
    low_stock: Optional[bool] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user)
):
    """List stationery items with optional filters"""
    try:
        query = supabase_admin.table("stationery_items").select("*")
        
        if category:
            query = query.eq("category", category)
        
        if low_stock is not None:
            if low_stock:
                query = query.filter("stock_quantity", "lte", "minimum_stock")
        
        query = query.range(offset, offset + limit - 1).order("name")
        response = query.execute()
        
        return [StationeryItemResponse(**item) for item in response.data]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch stationery items: {str(e)}"
        )

@router.post("/items", response_model=StationeryItemResponse, status_code=status.HTTP_201_CREATED)
async def create_stationery_item(
    item_data: StationeryItemCreate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Create a new stationery item"""
    try:
        response = supabase_admin.table("stationery_items").insert(item_data.model_dump()).execute()
        item = response.data[0]
        
        return StationeryItemResponse(**item)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create stationery item: {str(e)}"
        )

@router.get("/items/{item_id}", response_model=StationeryItemResponse)
async def get_stationery_item(
    item_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific stationery item"""
    try:
        response = supabase_admin.table("stationery_items").select("*").eq("id", item_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stationery item not found"
            )
        
        return StationeryItemResponse(**response.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch stationery item: {str(e)}"
        )

@router.put("/items/{item_id}", response_model=StationeryItemResponse)
async def update_stationery_item(
    item_id: str,
    item_data: StationeryItemUpdate,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Update a stationery item"""
    try:
        update_data = item_data.model_dump(exclude_unset=True)
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No update data provided"
            )
        
        response = supabase_admin.table("stationery_items").update(update_data).eq("id", item_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stationery item not found"
            )
        
        return StationeryItemResponse(**response.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update stationery item: {str(e)}"
        )

@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stationery_item(
    item_id: str,
    current_user: dict = Depends(require_role(["admin", "principal"]))
):
    """Delete a stationery item"""
    try:
        response = supabase_admin.table("stationery_items").delete().eq("id", item_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stationery item not found"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete stationery item: {str(e)}"
        )

# Stationery Distributions endpoints
@router.get("/distributions", response_model=List[StationeryDistributionResponse])
async def list_stationery_distributions(
    student_id: Optional[str] = Query(None),
    item_id: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_user)
):
    """List stationery distributions with optional filters"""
    try:
        query = supabase_admin.table("stationery_distributions").select("*")
        
        if student_id:
            query = query.eq("student_id", student_id)
        
        if item_id:
            query = query.eq("item_id", item_id)
        
        query = query.range(offset, offset + limit - 1).order("distributed_date", desc=True)
        response = query.execute()
        
        return [StationeryDistributionResponse(**distribution) for distribution in response.data]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch stationery distributions: {str(e)}"
        )

@router.post("/distributions", response_model=StationeryDistributionResponse, status_code=status.HTTP_201_CREATED)
async def create_stationery_distribution(
    distribution_data: StationeryDistributionCreate,
    current_user: dict = Depends(require_role(["admin", "principal", "teacher"]))
):
    """Create a new stationery distribution"""
    try:
        # Check if item has enough stock
        item_response = supabase_admin.table("stationery_items").select("stock_quantity").eq("id", distribution_data.item_id).execute()
        
        if not item_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stationery item not found"
            )
        
        current_stock = item_response.data[0]["stock_quantity"]
        if current_stock < distribution_data.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock. Available: {current_stock}, Requested: {distribution_data.quantity}"
            )
        
        # Create distribution record
        distribution_record = distribution_data.model_dump()
        distribution_record["distributed_by"] = current_user["id"]
        
        response = supabase_admin.table("stationery_distributions").insert(distribution_record).execute()
        distribution = response.data[0]
        
        # Update stock quantity
        new_stock = current_stock - distribution_data.quantity
        supabase_admin.table("stationery_items").update({"stock_quantity": new_stock}).eq("id", distribution_data.item_id).execute()
        
        return StationeryDistributionResponse(**distribution)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create stationery distribution: {str(e)}"
        )



