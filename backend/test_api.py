import requests
import sys

def test_api():
    try:
        r = requests.get('http://127.0.0.1:8000/registration/countries', timeout=5)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            countries = r.json()
            print(f"Count: {len(countries)}")
            if len(countries) > 0:
                print(f"First Country: {countries[0]}")
        else:
            print(f"Error Body: {r.text}")
    except Exception as e:
        print(f"Connection Error: {e}")

if __name__ == "__main__":
    test_api()
