---
description: "Unit and integration testing best practices with pytest"
applyTo: "**/*test*.py"
---

# Unit and Integration Tests Instructions

## Overview

This instruction file defines testing standards using pytest for Python projects.

## Test Organization

```
tests/
├── unit/
│   ├── domain/
│   │   └── test_order.py
│   └── application/
│       └── test_use_cases.py
├── integration/
│   ├── test_repositories.py
│   └── test_api.py
├── e2e/
│   └── test_order_flow.py
├── conftest.py
└── fixtures/
    └── factories.py
```

## Unit Tests

Test individual components in isolation without external dependencies.

```python
import pytest
from uuid import uuid4
from domain.order import Order, OrderItem, Money

class TestOrder:
    """Test domain logic without dependencies"""

    def test_add_item_to_pending_order(self):
        # Arrange
        order = Order(id=uuid4(), customer_id=uuid4())
        price = Money(10.0, "USD")

        # Act
        order.add_item("product-1", quantity=2, price=price)

        # Assert
        assert len(order.items) == 1
        assert order.items[0].quantity == 2

    def test_cannot_add_item_to_confirmed_order(self):
        # Arrange
        order = Order(id=uuid4(), customer_id=uuid4(), status="CONFIRMED")
        price = Money(10.0, "USD")

        # Act & Assert
        with pytest.raises(ValueError, match="Cannot modify confirmed order"):
            order.add_item("product-1", quantity=1, price=price)

    def test_calculate_total_with_multiple_items(self):
        # Arrange
        order = Order(id=uuid4(), customer_id=uuid4())
        order.add_item("p1", 2, Money(10.0, "USD"))
        order.add_item("p2", 1, Money(15.0, "USD"))

        # Act
        total = order.calculate_total()

        # Assert
        assert total.amount == 35.0
        assert total.currency == "USD"
```

## Integration Tests

Test interactions between components with real or in-memory infrastructure.

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from infrastructure.repositories.order_repository import SqlAlchemyOrderRepository
from domain.order import Order

@pytest.fixture
def db_session():
    """In-memory database for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    session.close()

class TestOrderRepository:
    """Test repository with real database"""

    def test_save_and_retrieve_order(self, db_session: Session):
        # Arrange
        repository = SqlAlchemyOrderRepository(db_session)
        order = Order(id=uuid4(), customer_id=uuid4())
        order.add_item("product-1", 1, Money(10.0, "USD"))

        # Act
        repository.save(order)
        retrieved = repository.get_by_id(order.id)

        # Assert
        assert retrieved is not None
        assert retrieved.id == order.id
        assert len(retrieved.items) == 1
```

## Fixtures and Factories

Use pytest fixtures and factory patterns for test data.

```python
# conftest.py
import pytest
from uuid import uuid4
from domain.order import Order, Money

@pytest.fixture
def customer_id():
    return uuid4()

@pytest.fixture
def pending_order(customer_id):
    """Reusable test fixture"""
    return Order(id=uuid4(), customer_id=customer_id)

@pytest.fixture
def order_with_items(pending_order):
    """Fixture composition"""
    pending_order.add_item("p1", 2, Money(10.0, "USD"))
    pending_order.add_item("p2", 1, Money(15.0, "USD"))
    return pending_order

# tests/test_order.py
def test_confirm_order_with_items(order_with_items):
    order_with_items.confirm()
    assert order_with_items.status == "CONFIRMED"
```

### Factory Pattern

```python
# tests/fixtures/factories.py
from dataclasses import replace
from uuid import uuid4
from domain.order import Order, Money

class OrderFactory:
    """Builder pattern for test objects"""

    @staticmethod
    def create(
        id=None,
        customer_id=None,
        status="PENDING",
        **kwargs
    ) -> Order:
        return Order(
            id=id or uuid4(),
            customer_id=customer_id or uuid4(),
            status=status,
            **kwargs
        )

    @staticmethod
    def with_items(base_order: Order, item_count: int = 3) -> Order:
        order = replace(base_order)
        for i in range(item_count):
            order.add_item(f"product-{i}", 1, Money(10.0, "USD"))
        return order
```

## Mocking

Use pytest-mock or unittest.mock for external dependencies.

```python
from unittest.mock import Mock
import pytest
from application.use_cases.apply_discount import ApplyDiscountUseCase
from domain.order import OrderId

def test_apply_discount_use_case():
    # Arrange
    mock_repository = Mock()
    order = OrderFactory.with_items(OrderFactory.create())
    mock_repository.get_by_id.return_value = order

    use_case = ApplyDiscountUseCase(mock_repository)

    # Act
    result = use_case.execute(order.id, discount=10.0)

    # Assert
    mock_repository.get_by_id.assert_called_once_with(order.id)
    mock_repository.save.assert_called_once()
    assert result.calculate_total().amount < order.calculate_total().amount
```

## Parametrized Tests

Test multiple scenarios efficiently.

```python
@pytest.mark.parametrize("quantity,price,expected", [
    (1, 10.0, 10.0),
    (2, 10.0, 20.0),
    (5, 7.5, 37.5),
])
def test_item_total(quantity, price, expected):
    item = OrderItem("product-1", quantity, Money(price, "USD"))
    total = item.price.multiply(item.quantity)
    assert total.amount == expected
```

## Test Naming Convention

Follow this pattern: `test_<unit>_<scenario>_<expected_result>`

Examples:

- `test_order_confirm_with_items_succeeds`
- `test_order_confirm_when_empty_raises_error`
- `test_repository_save_order_persists_to_database`

## Assertions

Use descriptive assertion messages:

```python
def test_order_total():
    order = OrderFactory.with_items(OrderFactory.create(), item_count=2)
    total = order.calculate_total()

    assert total.amount == 20.0, f"Expected total 20.0 but got {total.amount}"
```

## Coverage

Aim for high coverage but focus on meaningful tests:

```bash
# Run with coverage
pytest --cov=src --cov-report=html --cov-report=term

# Minimum coverage threshold
pytest --cov=src --cov-fail-under=80
```

## Async Testing

Use pytest-asyncio for async code:

```python
import pytest

@pytest.mark.asyncio
async def test_async_use_case():
    use_case = AsyncOrderUseCase()
    result = await use_case.execute(order_id)
    assert result is not None
```

## Markers

Organize tests with markers:

```python
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow",
    "integration: integration tests",
    "unit: unit tests",
]

# In test file
@pytest.mark.slow
@pytest.mark.integration
def test_large_data_processing():
    pass

# Run specific markers
# pytest -m "unit"
# pytest -m "not slow"
```

## Best Practices

1. **AAA Pattern**: Arrange, Act, Assert
2. **One assertion per test** (when possible)
3. **Test behavior, not implementation**
4. **Use descriptive test names**
5. **Keep tests independent**
6. **Fast unit tests** (<100ms each)
7. **Mock external services**
8. **Use factories for complex objects**

## Anti-Patterns to Avoid

❌ **Testing implementation details**

```python
def test_order_internal_list():
    order = Order(...)
    assert isinstance(order._items, list)  # Bad: testing internal detail
```

✅ **Testing behavior**

```python
def test_order_contains_added_item():
    order = Order(...)
    order.add_item("p1", 1, Money(10, "USD"))
    assert len(order.items) == 1  # Good: testing behavior
```

## Validation Checklist

- [ ] Tests follow AAA pattern
- [ ] Unit tests have no external dependencies
- [ ] Integration tests use test database
- [ ] Fixtures are reusable
- [ ] Test names are descriptive
- [ ] Coverage is above 80%
- [ ] All tests pass before committing
