set -eux
export ER_DB_CONNECTION="postgresql://asdf:asdf@localhost:2345/crdb"
python main.py > output_dot/new.dot && dot -Tpng ./output_dot/new.dot > ./output_image/new.png
