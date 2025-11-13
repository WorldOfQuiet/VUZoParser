from MyParser import UniversityDB


with UniversityDB('university_copy.db') as db:
    combined_search = db.get_records({
        'institute_name': 'яргу'
    })

print(combined_search)
