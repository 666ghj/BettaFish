# -*- coding: utf-8 -*-
"""
F2 购物清单接口。
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.family import FamilyMember
from app.models.shopping import ShoppingItem, HouseholdAgreement, ShoppingComment
from app.core.deps import get_current_member
from app.schemas.shopping import (
    ShoppingItemCreate, ShoppingItemUpdate, ShoppingItemOut,
    AgreementRequest, PurchaseRequest, CommentCreate,
)

router = APIRouter()


@router.get("/items", response_model=list[ShoppingItemOut])
async def list_shopping_items(
    list_type: str | None = None,
    status: str | None = None,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    if not member.family_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未加入家庭")

    query = select(ShoppingItem).where(ShoppingItem.family_id == member.family_id)
    if list_type:
        query = query.where(ShoppingItem.list_type == list_type)
    if status:
        query = query.where(ShoppingItem.status == status)
    query = query.order_by(ShoppingItem.created_at.desc())

    result = await db.execute(query)
    items = result.scalars().all()

    # 加载同意和评论数据
    output = []
    for item in items:
        agreements = await db.execute(
            select(HouseholdAgreement).where(HouseholdAgreement.shopping_item_id == item.id)
        )
        comments = await db.execute(
            select(ShoppingComment).where(ShoppingComment.shopping_item_id == item.id)
        )
        output.append(ShoppingItemOut(
            **item.__dict__,
            agreements=[{"member_id": a.member_id, "agreement": a.agreement} for a in agreements.scalars().all()],
            comments=[{"id": c.id, "content": c.content, "from_member_id": c.from_member_id} for c in comments.scalars().all()],
        ))
    return output


@router.post("/items", response_model=ShoppingItemOut)
async def create_shopping_item(
    req: ShoppingItemCreate,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    if not member.family_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未加入家庭")

    item = ShoppingItem(
        family_id=member.family_id,
        created_by=member.id,
        **req.model_dump(),
    )
    db.add(item)
    return ShoppingItemOut(**item.__dict__, agreements=[], comments=[])


@router.put("/items/{item_id}", response_model=ShoppingItemOut)
async def update_shopping_item(
    item_id: str,
    req: ShoppingItemUpdate,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ShoppingItem).where(
            ShoppingItem.id == item_id,
            ShoppingItem.family_id == member.family_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="物品不存在")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)

    return ShoppingItemOut(**item.__dict__, agreements=[], comments=[])


@router.delete("/items/{item_id}")
async def delete_shopping_item(
    item_id: str,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ShoppingItem).where(
            ShoppingItem.id == item_id,
            ShoppingItem.family_id == member.family_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="物品不存在")

    item.status = "cancelled"
    return {"message": "已取消"}


@router.post("/items/{item_id}/agree")
async def agree_shopping_item(
    item_id: str,
    req: AgreementRequest,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """同意/不同意购买"""
    existing = await db.execute(
        select(HouseholdAgreement).where(
            HouseholdAgreement.shopping_item_id == item_id,
            HouseholdAgreement.member_id == member.id,
        )
    )
    agreement = existing.scalar_one_or_none()
    if agreement:
        agreement.agreement = req.agreement
    else:
        agreement = HouseholdAgreement(
            shopping_item_id=item_id,
            member_id=member.id,
            agreement=req.agreement,
        )
        db.add(agreement)

    return {"message": "已记录"}


@router.post("/items/{item_id}/comment")
async def comment_shopping_item(
    item_id: str,
    req: CommentCreate,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    comment = ShoppingComment(
        shopping_item_id=item_id,
        from_member_id=member.id,
        **req.model_dump(),
    )
    db.add(comment)
    return {"message": "评论成功"}


@router.post("/items/{item_id}/purchase")
async def purchase_shopping_item(
    item_id: str,
    req: PurchaseRequest,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """标记已购买，自动关联 F3 收支记录"""
    result = await db.execute(
        select(ShoppingItem).where(
            ShoppingItem.id == item_id,
            ShoppingItem.family_id == member.family_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="物品不存在")

    item.status = "bought"
    item.actual_price = req.actual_price
    item.purchase_method = req.purchase_method
    item.purchase_date = req.purchase_date

    # 自动创建 F3 收支记录
    from app.models.finance import IncomeExpense
    ie = IncomeExpense(
        family_id=member.family_id,
        type="expense",
        amount=req.actual_price,
        category="shopping",
        note=f"购物: {item.name}",
        payer_id=member.id,
        record_date=req.purchase_date,
        source_type="shopping",
        source_id=item.id,
    )
    db.add(ie)
    await db.flush()
    item.income_expense_id = ie.id

    return {"message": "已标记为已购买，已自动记录到家庭收支", "income_expense_id": ie.id}