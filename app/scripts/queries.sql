# join two tables and group my drive model
sqlite3 app.db "select * from server_storage as S join storage_devices as D where S.device_id=D.id group by D.model;"

