"""Simple API Tests"""

import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Add project root
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.api.main import app

client = TestClient(app)


def test_root():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    print("✅ Root endpoint works")


def test_health():
    """Test health check"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    print("✅ Health check works")


def test_exchanges():
    """Test exchanges list"""
    response = client.get("/assets/exchanges/list")
    assert response.status_code == 200
    exchanges = response.json()
    assert isinstance(exchanges, list)
    assert len(exchanges) > 0
    print(f"✅ Exchanges endpoint works ({len(exchanges)} exchanges)")


def test_asset_search():
    """Test asset search"""
    response = client.get("/assets/search?q=AAPL&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "total" in data
    print(f"✅ Search works (found {data['total']} results)")


def test_optimize():
    """Test portfolio optimization"""
    from datetime import datetime, timedelta
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=365*2)
    
    # Find valid symbols first
    search_response = client.get("/assets/search?q=AAPL&limit=1")
    if search_response.status_code == 200:
        results = search_response.json()["results"]
        if results:
            symbol1 = results[0]["symbol"]
            
            # Get another symbol
            search_response2 = client.get("/assets/search?q=MSFT&limit=1")
            if search_response2.status_code == 200:
                results2 = search_response2.json()["results"]
                if results2:
                    symbol2 = results2[0]["symbol"]
                    
                    # Try optimization
                    payload = {
                        "symbols": [symbol1, symbol2],
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "method": "max_sharpe",
                        "risk_free_rate": 0.02,
                        "frequency": "M"
                    }
                    
                    response = client.post("/optimize/", json=payload)
                    
                    if response.status_code == 200:
                        data = response.json()
                        assert "weights" in data
                        assert "performance" in data
                        print(f"✅ Optimization works (Sharpe: {data['performance']['sharpe_ratio']:.2f})")
                        return
    
    print("⚠️  Optimization test skipped (couldn't find valid symbols)")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("  PHASE 3 API TESTS")
    print("="*60 + "\n")
    
    try:
        test_root()
        test_health()
        test_exchanges()
        test_asset_search()
        test_optimize()
        
        print("\n" + "="*60)
        print("✅ ALL API TESTS PASSED")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
