from MyParser import MyParser, SmoothTQDM, UniversityDB
import json

parser = MyParser()

def set_program_links():
    main_url = 'https://vuzoteka.ru/%D0%B2%D1%83%D0%B7%D1%8B/%D1%81%D0%BF%D0%B5%D1%86%D0%B8%D0%B0%D0%BB%D1%8C%D0%BD%D0%BE%D1%81%D1%82%D0%B8'
    direction_links = parser.get_direction_links_from_main_page(main_url)


    program_links = list()
    for link in SmoothTQDM(direction_links, ncols=80, smooth_window=1000, desc="Получение ссылок на программы"):
        while True:
            try:
                program_links += parser.get_educational_program_links_from_direction(link)
                break
            except Exception as e:
                print(f'Something wrong: {e}')

    with open('program_links.json', 'w', encoding='utf-8') as f:
        json.dump(program_links, f)


def set_institutes_information(start_index=0):
    with open('program_links.json', 'r', encoding='utf-8') as f:
        program_links = json.load(f)

    institutes_information = list()
    if start_index != 0:
        with open(f'institutes_information/institutes_information{start_index}.json', 'r', encoding='utf-8') as f:
            institutes_information = json.load(f)

    for index in SmoothTQDM(range(start_index, len(program_links)), ncols=80, smooth_window=1000, desc="Получение информации о программах"):
        link = program_links[index]
        if index%4000==0:
            with open(f'institutes_information/institutes_information{index}.json', 'w', encoding='utf-8') as f:
                json.dump(institutes_information, f)

        try: institutes_information += [parser.get_institute_information_from_institute_page(link)]
        except Exception: pass

    with open('institutes_information/institutes_information.json', 'w', encoding='utf-8') as f:
        json.dump(list(institutes_information), f)


def set_data_base():
    with open('institutes_information/institutes_information.json', 'r', encoding='utf-8') as f:
        institutes_information = json.load(f)

    with UniversityDB() as db:
        db.clear_database()
        for item in SmoothTQDM(institutes_information, ncols=80, smooth_window=1000, desc="Запись в БД"):
            db.insert_record(item)



set_program_links()
set_institutes_information()
set_data_base()
