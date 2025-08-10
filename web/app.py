from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
import os
from utils.logger import logger
from utils.data_manager import load_json_data, save_json_data

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def register_routes(bot):
    tarot_file = os.path.join(bot.data_dir, 'tarot.json')
    fortune_file = os.path.join(bot.data_dir, 'fortune.json')

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/health')
    def health():
        return {"status": "healthy", "bot_ready": bot.is_ready() if hasattr(bot, 'is_ready') else False}

    @app.route('/tarot', methods=['GET', 'POST'])
    def tarot_web():
        try:
            tarot_cards = load_json_data(tarot_file)
            if request.method == 'POST':
                for card in tarot_cards:
                    upright_desc = request.form.get(f'upright_{card["id"]}')
                    if upright_desc is not None:
                        card['description']['upright'] = upright_desc
                    
                    reversed_desc = request.form.get(f'reversed_{card["id"]}')
                    if reversed_desc is not None:
                        card['description']['reversed'] = reversed_desc

                    file_key = f'image_upload_{card["id"]}'
                    if file_key in request.files:
                        file = request.files[file_key]
                        if file and file.filename and allowed_file(file.filename):
                            filename = secure_filename(f"tarot_{card['id']}{os.path.splitext(file.filename)[1]}")
                            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                            file.save(save_path)
                            card['image'] = os.path.join(UPLOAD_FOLDER, filename).replace(os.path.sep, '/')
                
                save_json_data(tarot_file, tarot_cards)
                return redirect(url_for('tarot_web'))
            return render_template('tarot.html', tarot_cards=tarot_cards)
        except Exception as e:
            logger.error(f"Error in tarot_web: {e}")
            return "Error loading tarot data", 500

    @app.route('/fortune', methods=['GET', 'POST'])
    def fortune_web():
        try:
            fortune_data = load_json_data(fortune_file)
            if request.method == 'POST':
                form_type = request.form.get('form_type')

                if form_type == 'levels':
                    for level in fortune_data['levels']:
                        level_id = level['id']
                        level['level_name'] = request.form.get(f'level_name_{level_id}', level['level_name'])
                        level['stars'] = int(request.form.get(f'stars_{level_id}', level['stars']))
                        level['star_shape'] = request.form.get(f'star_shape_{level_id}', level['star_shape'])
                        level['image'] = request.form.get(f'image_{level_id}', '')
                        level['good_events'] = int(request.form.get(f'good_events_{level_id}', 2))
                        level['bad_events'] = int(request.form.get(f'bad_events_{level_id}', 2))

                elif form_type == 'activities':
                    pool_name = request.form.get('pool_name')
                    if pool_name in fortune_data['activities']:
                        # Handle deletion
                        if 'delete_activity' in request.form:
                            activity_name_to_delete = request.form.get('delete_activity')
                            fortune_data['activities'][pool_name] = [a for a in fortune_data['activities'][pool_name] if a['name'] != activity_name_to_delete]
                        # Handle addition
                        elif 'new_name' in request.form and 'new_description' in request.form:
                            new_name = request.form.get('new_name')
                            new_description = request.form.get('new_description')
                            if new_name and new_description:
                                fortune_data['activities'][pool_name].append({'name': new_name, 'description': new_description})
                        # Handle updates
                        else:
                            for i, activity in enumerate(fortune_data['activities'][pool_name]):
                                original_name = request.form.get(f'original_name_{i}')
                                activity['name'] = request.form.get(f'name_{i}', original_name)
                                activity['description'] = request.form.get(f'description_{i}', activity['description'])

                elif form_type == 'domains':
                    for domain in fortune_data['domains']:
                        domain_name = domain['name']
                        for level in fortune_data['levels']:
                            level_name = level['level_name']
                            key = f"domain_{domain_name}_{level_name}"
                            domain['fortunes'][level_name] = request.form.get(key, domain['fortunes'].get(level_name, ''))
                
                elif form_type == 'connectors':
                    fortune_data['connectors']['intro'] = request.form.get('intro', '').split(',')
                    fortune_data['connectors']['outro_good'] = request.form.get('outro_good', '').split(',')
                    fortune_data['connectors']['outro_neutral'] = request.form.get('outro_neutral', '').split(',')
                    fortune_data['connectors']['outro_bad'] = request.form.get('outro_bad', '').split(',')

                save_json_data(fortune_file, fortune_data)
                return redirect(url_for('fortune_web'))
                
            return render_template('fortune.html', fortune_data=fortune_data)
        except Exception as e:
            logger.error(f"Error in fortune_web: {e}")
            return "Error loading fortune data", 500
    
    return app
