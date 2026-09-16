"""categoryCode2를 호출해 대/중/소분류 코드를 전부 출력하는 1회성 조회 스크립트.

실행 전 .env에 PET_TOUR_API_KEY를 설정해야 한다.
출력 결과를 보고 식당/카페/산책/액티비티에 해당하는 정확한 cat1/cat2/cat3 값을
app/domains/places/constants.py의 CATEGORY_SEARCH_PARAMS에 반영할 것.

실행: uv run python -m scripts.discover_pet_tour_categories
"""

import asyncio

from app.domains.places.external.pet_tour_client import PetTourClient


async def main() -> None:
    async with PetTourClient() as client:
        cat1_list = await client.category_code()
        print("=== 대분류 (cat1) ===")
        for cat1 in cat1_list:
            print(cat1.get("code"), cat1.get("name"))

        for cat1 in cat1_list:
            code1 = cat1.get("code")
            cat2_list = await client.category_code(cat1=code1)
            print(f"\n=== 중분류 (cat1={code1} {cat1.get('name')}) ===")
            for cat2 in cat2_list:
                print(cat2.get("code"), cat2.get("name"))

            for cat2 in cat2_list:
                code2 = cat2.get("code")
                cat3_list = await client.category_code(cat1=code1, cat2=code2)
                print(f"\n--- 소분류 (cat1={code1}, cat2={code2} {cat2.get('name')}) ---")
                for cat3 in cat3_list:
                    print(cat3.get("code"), cat3.get("name"))


if __name__ == "__main__":
    asyncio.run(main())
