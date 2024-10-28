from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify
import os
from werkzeug.utils import secure_filename
from flask import send_from_directory
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
# Configure PostgreSQL Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg2://postgres:984832rodriguez@localhost:5432/Inventory'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Example in-memory storage for demonstration
material_data = []
material_log_data = []
waste_log_data = []
orders = []

# Initialize the database connection
db = SQLAlchemy(app)


# Define Inventory model
class Inventory(db.Model):
    __tablename__ = 'inventory'
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(100), nullable=False)
    uoi = db.Column(db.String(50), nullable=False)
    beginning = db.Column(db.Integer, nullable=False)
    incoming = db.Column(db.Integer, nullable=False)
    outgoing = db.Column(db.Integer, nullable=False)
    waste = db.Column(db.Integer, nullable=False)
    ending = db.Column(db.Integer, nullable=False)
    date = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f"<Inventory {self.item}>"


# Define PurchaseRecord model
class PurchaseRecord(db.Model):
    __tablename__ = 'purchase_records'

    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    receipt_url = db.Column(db.String(200), nullable=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)


class TotalExpenses(db.Model):
    __tablename__ = 'total_expenses'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"<TotalExpenses {self.total_amount} on {self.date}>"


# Create database tables
with app.app_context():
    db.create_all()


@app.route('/')
def dashboard():
    return render_template('dashboard.html')


@app.route('/inventory', methods=['GET', 'POST'])
def inventory():
    search_query = request.args.get('search', '').strip().lower()
    if search_query:
        filtered_inventory = Inventory.query.filter(Inventory.item.ilike(f'%{search_query}%')).all()
    else:
        filtered_inventory = Inventory.query.all()

    # Define the threshold for stock levels
    stock_threshold = 10
    alerts = []

    # Check for items that are below the threshold and add to alerts
    for item in filtered_inventory:
        try:
            # Trigger an alert if the stock level is below or equal to the threshold
            if item.ending <= stock_threshold:
                alerts.append({
                    'item': item.item,
                    'current_stock': item.ending
                })
        except ValueError:
            print(f"Error: The 'ending' value for item {item.item} is not a valid number.")

    date_today = datetime.now().strftime('%d %B %Y')

    return render_template('inventory.html', inventory=filtered_inventory, date_today=date_today, alerts=alerts)


@app.route('/view_inventory', methods=['GET'])
def view_inventory():
    # Get the date from query parameters
    date = request.args.get('date')

    # Default to today's date if no date is provided
    if date:
        try:
            search_date = datetime.strptime(date, '%Y-%m-%d').strftime('%d %B %Y')
        except ValueError:
            search_date = None
    else:
        search_date = datetime.now().strftime('%d %B %Y')

    # Filter inventory based on the search_date
    filtered_inventory = Inventory.query.filter_by(date=search_date).all()

    return render_template('view_inventory.html', inventory=filtered_inventory,
                           date_today=datetime.now().strftime('%Y-%m-%d'))


@app.route('/add_inventory', methods=['GET', 'POST'])
def add_inventory():
    if request.method == 'POST':
        item = request.form['item']
        uoi = request.form['uoi']
        beginning = int(request.form['beginning'])
        incoming = int(request.form['incoming'])
        outgoing = int(request.form['outgoing'])
        waste = int(request.form['waste'])

        # Automatically calculate the ending balance
        ending = beginning + incoming - outgoing - waste

        new_item = Inventory(
            item=item,
            uoi=uoi,
            beginning=beginning,
            incoming=incoming,
            outgoing=outgoing,
            waste=waste,
            ending=ending,  # Use the calculated ending balance
            date=datetime.now().strftime('%d %B %Y')
        )
        db.session.add(new_item)
        db.session.commit()

        return redirect(url_for('inventory'))


@app.route('/edit_inventory/<int:item_id>', methods=['GET', 'POST'])
def edit_inventory(item_id):
    item = Inventory.query.get_or_404(item_id)

    if request.method == 'POST':
        item.item = request.form['item']
        item.uoi = request.form['uoi']
        beginning = int(request.form['beginning'])
        incoming = int(request.form['incoming'])
        outgoing = int(request.form['outgoing'])
        waste = int(request.form['waste'])

        # Automatically calculate the ending balance
        item.ending = beginning + incoming - outgoing - waste

        item.beginning = beginning
        item.incoming = incoming
        item.outgoing = outgoing
        item.waste = waste

        db.session.commit()
        return redirect(url_for('inventory'))

    return jsonify({
        'id': item.id,
        'item': item.item,
        'uoi': item.uoi,
        'beginning': item.beginning,
        'incoming': item.incoming,
        'outgoing': item.outgoing,
        'waste': item.waste,
        'ending': item.ending
    })


@app.route('/delete_inventory/<int:item_id>', methods=['POST'])
def delete_inventory(item_id):
    item = Inventory.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('inventory'))


# Define the path to store uploaded images
UPLOAD_FOLDER = 'uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


@app.route('/get_waste_log', methods=['GET', 'POST'])
def get_waste_log():
    search_query = request.args.get('search', '').strip().lower()

    if search_query:
        filtered_waste_log = [item for item in waste_log_data if search_query in item['item'].lower()]
    else:
        filtered_waste_log = waste_log_data

    date_today = datetime.now().strftime('%d %B %Y')

    return render_template('waste_log.html', waste_log=filtered_waste_log, date_today=date_today)


@app.route('/view_waste', methods=['GET'])
def view_waste():
    date = request.args.get('date')

    if date:
        try:
            search_date = datetime.strptime(date, '%Y-%m-%d').strftime('%d %B %Y')
        except ValueError:
            search_date = None
    else:
        search_date = datetime.now().strftime('%d %B %Y')

    filtered_waste = [item for item in waste_log_data if item.get('date') == search_date]

    return render_template('view_waste.html', waste_log=filtered_waste,
                           date_today=datetime.now().strftime('%Y-%m-%d'))


@app.route('/add_waste', methods=['GET', 'POST'])
def add_waste():
    if request.method == 'POST':
        item = request.form['item']
        uoi = request.form['uoi']
        quantity = request.form['quantity']
        description = request.form['description']

        # Handle file upload
        image = request.files.get('image')
        image_url = ''
        if image:
            image_filename = secure_filename(image.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            image.save(image_path)
            image_url = url_for('uploaded_file', filename=image_filename)

        new_waste = {
            'id': len(waste_log_data) + 1,
            'item': item,
            'uoi': uoi,
            'quantity': quantity,
            'description': description,
            'date': datetime.now().strftime('%d %B %Y'),
            'image_url': image_url
        }
        waste_log_data.append(new_waste)
        return redirect(url_for('get_waste_log'))


@app.route('/edit_waste/<int:item_id>', methods=['GET', 'POST'])
def edit_waste(item_id):
    item = next((item for item in waste_log_data if item['id'] == item_id), None)

    if not item:
        return redirect(url_for('get_waste_log'))

    if request.method == 'POST':
        item['item'] = request.form['item']
        item['uoi'] = request.form['uoi']
        item['quantity'] = request.form['quantity']
        item['description'] = request.form['description']

        # Handle file upload
        image = request.files.get('image')
        if image:
            image_filename = secure_filename(image.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            image.save(image_path)
            item['image_url'] = url_for('uploaded_file', filename=image_filename)

        return redirect(url_for('get_waste_log'))

    return jsonify(item)


@app.route('/delete_waste/<int:item_id>', methods=['POST'])
def delete_waste(item_id):
    global waste_log_data
    waste_log_data = [item for item in waste_log_data if item['id'] != item_id]
    return redirect(url_for('get_waste_log'))


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/material', methods=['GET', 'POST'])
def material():
    search_query = request.args.get('search', '').strip().lower()
    if search_query:
        filtered_material = [item for item in material_data if search_query in item['item'].lower()]
    else:
        filtered_material = material_data

    stock_threshold = 10
    alerts = []

    for item in filtered_material:
        try:
            ending_stock = int(item['ending'])
            if ending_stock <= stock_threshold:
                alerts.append({
                    'item': item['item'],
                    'current_stock': ending_stock
                })
        except ValueError:
            print(f"Error: The 'ending' value for item {item['item']} is not a valid number.")

    date_today = datetime.now().strftime('%d %B %Y')

    return render_template('material.html', material=filtered_material, date_today=date_today, alerts=alerts)


@app.route('/view_material', methods=['GET'])
def view_material():
    # Get the date from query parameters
    date = request.args.get('date')

    # Default to today's date if no date is provided
    if date:
        try:
            search_date = datetime.strptime(date, '%Y-%m-%d').strftime('%d %B %Y')
        except ValueError:
            search_date = None
    else:
        search_date = datetime.now().strftime('%d %B %Y')

    print(f"Search Date: {search_date}")  # Debugging output

    # Filter material based on the search_date
    filtered_material = [item for item in material_data if item.get('date') == search_date]

    print(f"Filtered Material: {filtered_material}")  # Debugging output

    return render_template('view_material.html', material=filtered_material,
                           date_today=datetime.now().strftime('%Y-%m-%d'))


@app.route('/add_material', methods=['GET', 'POST'])
def add_material():
    if request.method == 'POST':
        item = request.form['item']
        uoi = request.form['uoi']
        beginning = int(request.form['beginning'])
        incoming = int(request.form['incoming'])
        outgoing = int(request.form['outgoing'])
        waste = int(request.form['waste'])

        # Automatically calculate the ending balance
        ending = beginning + incoming - outgoing - waste

        new_item = {
            'id': len(material_data) + 1,
            'item': item,
            'uoi': uoi,
            'beginning': beginning,
            'incoming': incoming,
            'outgoing': outgoing,
            'waste': waste,
            'ending': ending,  # Use the calculated ending balance
            'date': datetime.now().strftime('%d %B %Y')
        }
        material_data.append(new_item)
        return redirect(url_for('material'))


@app.route('/edit_material/<int:item_id>', methods=['GET', 'POST'])
def edit_material(item_id):
    # Find the material item with the given item_id
    item = next((item for item in material_data if item['id'] == item_id), None)

    # If item not found, redirect to the material page
    if not item:
        return redirect(url_for('material'))

    if request.method == 'POST':
        # Update the material entry with the new data from the form
        beginning = int(request.form['beginning'])
        incoming = int(request.form['incoming'])
        outgoing = int(request.form['outgoing'])
        waste = int(request.form['waste'])

        # Automatically calculate the ending balance
        ending = beginning + incoming - outgoing - waste

        item['item'] = request.form['item']
        item['uoi'] = request.form['uoi']
        item['beginning'] = beginning
        item['incoming'] = incoming
        item['outgoing'] = outgoing
        item['waste'] = waste
        item['ending'] = ending  # Use the calculated ending balance

        # Redirect to the material page after saving the changes
        return redirect(url_for('material'))

    # For GET request, return the item data as a JSON response
    return jsonify(item)


@app.route('/delete_material/<int:item_id>', methods=['POST'])
def delete_material(item_id):
    global material_data
    material_data = [item for item in material_data if item['id'] != item_id]
    return redirect(url_for('material'))


@app.route('/get_material_log', methods=['GET', 'POST'])
def get_material_log():
    search_query = request.args.get('search', '').strip().lower()

    if search_query:
        filtered_material_log = [item for item in material_log_data if search_query in item['item'].lower()]
    else:
        filtered_material_log = material_log_data

    date_today = datetime.now().strftime('%d %B %Y')

    return render_template('material_log.html', material_log=filtered_material_log, date_today=date_today)


@app.route('/view_material_log', methods=['GET'])
def view_material_log():
    # Get the date from query parameters
    date = request.args.get('date')

    # Default to today's date if no date is provided
    if date:
        try:
            search_date = datetime.strptime(date, '%Y-%m-%d').strftime('%d %B %Y')
        except ValueError:
            search_date = None
    else:
        search_date = datetime.now().strftime('%d %B %Y')

    # Filter material log based on the search_date
    filtered_material_log = [item for item in material_log_data if item.get('date') == search_date]

    return render_template('view_material_log.html', material_log=filtered_material_log,
                           date_today=datetime.now().strftime('%Y-%m-%d'))


@app.route('/add_material_log', methods=['GET', 'POST'])
def add_material_log():
    if request.method == 'POST':
        item = request.form['item']
        uoi = request.form['uoi']
        quantity = request.form['quantity']
        description = request.form['description']

        # Handle file upload
        image = request.files.get('image')
        image_url = ''
        if image:
            image_filename = secure_filename(image.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            image.save(image_path)
            image_url = url_for('uploaded_file', filename=image_filename)

        new_material_log = {
            'id': len(material_log_data) + 1,
            'item': item,
            'uoi': uoi,
            'quantity': quantity,
            'description': description,
            'date': datetime.now().strftime('%d %B %Y'),
            'image_url': image_url
        }
        material_log_data.append(new_material_log)
        return redirect(url_for('get_material_log'))


@app.route('/edit_material_log/<int:item_id>', methods=['GET', 'POST'])
def edit_material_log(item_id):
    # Find the material log item with the given item_id
    item = next((item for item in material_log_data if item['id'] == item_id), None)

    # If item not found, redirect to the material log page
    if not item:
        return redirect(url_for('get_material_log'))

    if request.method == 'POST':
        # Update the material log entry with the new data from the form
        item['item'] = request.form['item']
        item['uoi'] = request.form['uoi']
        item['quantity'] = request.form['quantity']
        item['description'] = request.form['description']

        # Handle file upload
        image = request.files.get('image')
        if image:
            image_filename = secure_filename(image.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            image.save(image_path)
            item['image_url'] = url_for('uploaded_file', filename=image_filename)

        # Redirect to the material log page after saving the changes
        return redirect(url_for('get_material_log'))

    # For GET request, return the item data as a JSON response
    return jsonify(item)


@app.route('/delete_material_log/<int:item_id>', methods=['POST'])
def delete_material_log(item_id):
    global material_log_data
    material_log_data = [item for item in material_log_data if item['id'] != item_id]
    return redirect(url_for('get_material_log'))


@app.route('/order_report')
def order_report():
    # Get today's date for display in the format: "DD Month YYYY" (e.g., 25 September 2024)
    date_today = datetime.now().strftime('%d %B %Y')

    # Get the search query from the URL if present
    search_query = request.args.get('search', '').strip()

    # Filter orders if a search query exists (based on Order No.)
    if search_query:
        filtered_orders = [order for order in orders if search_query.lower() in order['order_id'].lower()]
    else:
        filtered_orders = orders

    # Render the order report template with the date, filtered orders, and search query
    return render_template(
        'order_report.html',
        date_today=date_today,
        orders=filtered_orders,
        search_query=search_query
    )


@app.route('/delete_order/<string:order_id>', methods=['POST'])
def delete_order(order_id):
    global orders  # Assuming orders is a global list or dictionary

    # Remove the order with the matching order_id
    orders = [order for order in orders if order['order_id'] != order_id]

    # Redirect back to the order report page after deletion
    return redirect(url_for('order_report'))


@app.route('/order-form', methods=['GET', 'POST'])
def order_form():
    if request.method == 'POST':
        # Retrieve form data
        order_id = request.form.get('order_id')
        prepared_by = request.form.get('prepared_by')
        checked_by = request.form.get('checked_by')
        date = request.form.get('date')
        time = request.form.get('time')
        store_branch = request.form.get('store_branch')
        status = request.form.get('status')

        # Wet Items
        wet_items = request.form.getlist('wet_item[]')
        wet_uoi = request.form.getlist('wet_item_uoi[]')
        wet_qty = request.form.getlist('wet_item_qty[]')
        wet_prepared = request.form.getlist('wet_item_prepared[]')
        wet_received = request.form.getlist('wet_item_received[]')

        # Sauce/Spice/Dry
        sauce_items = request.form.getlist('sauce_item[]')
        sauce_uoi = request.form.getlist('sauce_item_uoi[]')
        sauce_qty = request.form.getlist('sauce_item_qty[]')
        sauce_prepared = request.form.getlist('sauce_item_prepared[]')
        sauce_received = request.form.getlist('sauce_item_received[]')

        # Ice Cream
        ice_cream_items = request.form.getlist('ice_cream_item[]')
        ice_cream_uoi = request.form.getlist('ice_cream_item_uoi[]')
        ice_cream_qty = request.form.getlist('ice_cream_item_qty[]')
        ice_cream_prepared = request.form.getlist('ice_cream_item_prepared[]')
        ice_cream_received = request.form.getlist('ice_cream_item_received[]')

        # Shakes
        shakes_items = request.form.getlist('shakes_item[]')
        shakes_uoi = request.form.getlist('shakes_item_uoi[]')
        shakes_qty = request.form.getlist('shakes_item_qty[]')
        shakes_prepared = request.form.getlist('shakes_item_prepared[]')
        shakes_received = request.form.getlist('shakes_item_received[]')

        # Vegetables
        vegetables_items = request.form.getlist('vegetables_item[]')
        vegetables_uoi = request.form.getlist('vegetables_item_uoi[]')
        vegetables_qty = request.form.getlist('vegetables_item_qty[]')
        vegetables_prepared = request.form.getlist('vegetables_item_prepared[]')
        vegetables_received = request.form.getlist('vegetables_item_received[]')

        # Packaging
        packaging_items = request.form.getlist('packaging_item[]')
        packaging_uoi = request.form.getlist('packaging_item_uoi[]')
        packaging_qty = request.form.getlist('packaging_item_qty[]')
        packaging_prepared = request.form.getlist('packaging_item_prepared[]')
        packaging_received = request.form.getlist('packaging_item_received[]')

        # Groceries
        groceries_items = request.form.getlist('groceries_item[]')
        groceries_uoi = request.form.getlist('groceries_item_uoi[]')
        groceries_qty = request.form.getlist('groceries_item_qty[]')
        groceries_prepared = request.form.getlist('groceries_item_prepared[]')
        groceries_received = request.form.getlist('groceries_item_received[]')

        # Manual Request
        manual_items = request.form.getlist('manual_item[]')
        manual_uoi = request.form.getlist('manual_item_uoi[]')
        manual_qty = request.form.getlist('manual_item_qty[]')
        manual_prepared = request.form.getlist('manual_item_prepared[]')
        manual_received = request.form.getlist('manual_item_received[]')

        # Create an order dictionary to store the order data
        order = {
            'order_id': order_id,
            'prepared_by': prepared_by,
            'checked_by': checked_by,
            'date': date,
            'time': time,
            'store_branch': store_branch,
            'status': status,
            'wet_items': list(zip(wet_items, wet_uoi, wet_qty, wet_prepared, wet_received)),
            'sauce_items': list(zip(sauce_items, sauce_uoi, sauce_qty, sauce_prepared, sauce_received)),
            'ice_cream_items': list(
                zip(ice_cream_items, ice_cream_uoi, ice_cream_qty, ice_cream_prepared, ice_cream_received)),
            'shakes_items': list(zip(shakes_items, shakes_uoi, shakes_qty, shakes_prepared, shakes_received)),
            'vegetables_items': list(
                zip(vegetables_items, vegetables_uoi, vegetables_qty, vegetables_prepared, vegetables_received)),
            'packaging_items': list(
                zip(packaging_items, packaging_uoi, packaging_qty, packaging_prepared, packaging_received)),
            'groceries_items': list(
                zip(groceries_items, groceries_uoi, groceries_qty, groceries_prepared, groceries_received)),
            'manual_items': list(zip(manual_items, manual_uoi, manual_qty, manual_prepared, manual_received))
        }

        # Append order data to the orders list
        orders.append(order)

        # Redirect to the order report page or another page after submission
        return redirect(url_for('order_report'))

    # Render the order form template
    return render_template('order_form.html')


@app.route('/view_order/<order_id>', methods=['GET'])
def view_order(order_id):
    # Find the order matching the provided order_id
    order = next((o for o in orders if o['order_id'] == order_id), None)

    # If the order is not found, handle it by returning an error message or redirecting
    if not order:
        return "Order not found", 404

    # Render the order details template
    return render_template('view_order.html', order=order)


@app.route('/commissary')
def commissary():
    date_today = datetime.now().strftime('%d %B %Y')
    return render_template('commissary.html', date_today=date_today)


@app.route('/purchase_records')
def purchase_records():
    date_today = datetime.now().strftime('%d %B %Y')
    purchases = PurchaseRecord.query.all()

    # Get total expenses for today
    total_expenses_today = TotalExpenses.query.filter_by(date=datetime.utcnow().date()).first()
    total_expenses = total_expenses_today.total_amount if total_expenses_today else 0

    return render_template('purchase_records.html', date_today=date_today, purchase_records=purchases,
                           total_expenses=total_expenses)


@app.route('/add_purchase', methods=['GET', 'POST'])
def add_purchase():
    if request.method == 'POST':
        # Get the form data
        item = request.form['item']
        quantity = int(request.form['quantity'])
        unit_price = float(request.form['unit_price'])

        # Calculate the total price
        total_price = quantity * unit_price

        # Handle receipt file upload
        receipt = request.files.get('receipt')
        receipt_url = ''
        if receipt:
            receipt_filename = secure_filename(receipt.filename)
            receipt_path = os.path.join(app.config['UPLOAD_FOLDER'], receipt_filename)
            receipt.save(receipt_path)
            receipt_url = url_for('uploaded_file', filename=receipt_filename)

        # Add the new purchase to the database
        new_purchase = PurchaseRecord(
            item=item,
            quantity=quantity,
            unit_price=unit_price,
            total_price=total_price,
            receipt_url=receipt_url
        )
        db.session.add(new_purchase)

        # Update total expenses
        total_expenses_today = TotalExpenses.query.filter_by(date=datetime.utcnow().date()).first()
        if total_expenses_today:
            # Update existing total
            total_expenses_today.total_amount += total_price
        else:
            # Create a new total record
            total_expenses_today = TotalExpenses(date=datetime.utcnow().date(), total_amount=total_price)
            db.session.add(total_expenses_today)

        db.session.commit()

        return redirect(url_for('purchase_records'))

    return render_template('add_purchase.html')


@app.route('/edit_purchase/<int:purchase_id>', methods=['GET', 'POST'])
def edit_purchase(purchase_id):
    # Find the purchase record by its ID
    purchase = PurchaseRecord.query.get_or_404(purchase_id)

    if request.method == 'POST':
        # Update the form data
        purchase.item = request.form['item']
        purchase.quantity = int(request.form['quantity'])
        purchase.unit_price = float(request.form['unit_price'])

        # Calculate the updated total price
        purchase.total_price = purchase.quantity * purchase.unit_price

        # Handle receipt file upload (if a new one is provided)
        receipt = request.files.get('receipt')
        if receipt:
            receipt_filename = secure_filename(receipt.filename)
            receipt_path = os.path.join(app.config['UPLOAD_FOLDER'], receipt_filename)
            receipt.save(receipt_path)
            purchase.receipt_url = url_for('uploaded_file', filename=receipt_filename)

        # Commit the changes to the database
        db.session.commit()

        return redirect(url_for('purchase_records'))

    # If GET request, return data for editing
    return render_template('edit_purchase.html', purchase=purchase)


@app.route('/delete_purchase/<int:purchase_id>', methods=['POST'])
def delete_purchase(purchase_id):
    # Find the purchase record by its ID
    purchase = PurchaseRecord.query.get_or_404(purchase_id)

    # Delete the purchase record
    db.session.delete(purchase)
    db.session.commit()

    return redirect(url_for('purchase_records'))


@app.route('/logout')
def logout():
    return "Logged out"


if __name__ == '__main__':
    app.run(debug=True)
