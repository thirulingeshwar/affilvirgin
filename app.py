import uuid
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId
import os

# ==================================================
# FLASK APP
# ==================================================
app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

# ==================================================
# MONGODB CONNECTION
# ==================================================
MONGO_URI = "mongodb+srv://thirulingeshwart_db_user:FzZ99iWl3yQGvh26@cluster0.hc1wf7k.mongodb.net/?appName=Cluster0"

# For local MongoDB, use:
# MONGO_URI = "mongodb://localhost:27017"

# Try to connect to MongoDB
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db = client.attendance_db
    students_col = db.students
    attendance_col = db.records
    print("✅ MongoDB Connected Successfully!")
except Exception as e:
    print(f"⚠️ MongoDB Connection Failed: {e}")
    print("⚠️ Using in-memory storage as fallback...")
    # Fallback to in-memory storage if MongoDB is not available
    students_col = None
    attendance_col = None
    in_memory_students = []
    in_memory_attendance = []

# Create indexes for better performance (only if MongoDB is connected)
if students_col is not None:
    try:
        students_col.create_index("id", unique=True)
        attendance_col.create_index("id", unique=True)
        attendance_col.create_index([("studentId", 1), ("date", 1)])
        print("✅ Database indexes created")
    except:
        pass

# ==================================================
# HELPER FUNCTIONS FOR IN-MEMORY STORAGE (FALLBACK)
# ==================================================
def get_all_students():
    if students_col is not None:
        return list(students_col.find({}, {"_id": 0}))
    else:
        return in_memory_students

def save_student(student):
    if students_col is not None:
        students_col.insert_one(student)
    else:
        in_memory_students.append(student)
    return student

def update_student(student_id, updates):
    if students_col is not None:
        students_col.update_one({"id": student_id}, {"$set": updates})
    else:
        for s in in_memory_students:
            if s["id"] == student_id:
                for key, value in updates.items():
                    s[key] = value
                break

def delete_student(student_id):
    if students_col is not None:
        students_col.delete_one({"id": student_id})
    else:
        global in_memory_students
        in_memory_students = [s for s in in_memory_students if s["id"] != student_id]

def get_all_attendance():
    if attendance_col is not None:
        return list(attendance_col.find({}, {"_id": 0}))
    else:
        return in_memory_attendance

def save_attendance(record):
    if attendance_col is not None:
        existing = attendance_col.find_one({"studentId": record["studentId"], "date": record["date"]})
        if existing:
            attendance_col.update_one({"_id": existing["_id"]}, {"$set": record})
        else:
            attendance_col.insert_one(record)
    else:
        global in_memory_attendance
        existing_index = None
        for i, r in enumerate(in_memory_attendance):
            if r["studentId"] == record["studentId"] and r["date"] == record["date"]:
                existing_index = i
                break
        if existing_index is not None:
            in_memory_attendance[existing_index] = record
        else:
            in_memory_attendance.append(record)
    return record

def delete_attendance(record_id):
    if attendance_col is not None:
        attendance_col.delete_one({"id": record_id})
    else:
        global in_memory_attendance
        in_memory_attendance = [r for r in in_memory_attendance if r["id"] != record_id]

def update_attendance(record_id, updates):
    if attendance_col is not None:
        attendance_col.update_one({"id": record_id}, {"$set": updates})
    else:
        for r in in_memory_attendance:
            if r["id"] == record_id:
                for key, value in updates.items():
                    r[key] = value
                break

def count_documents(collection):
    if collection == "students":
        if students_col is not None:
            return students_col.count_documents({})
        else:
            return len(in_memory_students)
    else:
        if attendance_col is not None:
            return attendance_col.count_documents({})
        else:
            return len(in_memory_attendance)

def filter_attendance_by_date(date):
    if attendance_col is not None:
        return list(attendance_col.find({"date": date}))
    else:
        return [r for r in in_memory_attendance if r.get("date") == date]

def filter_attendance_by_status(status):
    if attendance_col is not None:
        return list(attendance_col.find({"status": status}))
    else:
        return [r for r in in_memory_attendance if r.get("status") == status]

# ==================================================
# FRONTEND ROUTE
# ==================================================
@app.route("/")
def home():
    return send_from_directory("static", "index.html")


# ==================================================
# STUDENT API
# ==================================================
@app.route("/api/students", methods=["GET", "POST"])
def students():
    if request.method == "POST":
        data = request.json
        
        student = {
            "id": str(uuid.uuid4())[:8],
            "name": data.get("name", ""),
            "branch": data.get("branch", ""),
            "class": data.get("class", ""),
            "days": data.get("days", []),
            "inTime": data.get("inTime", "09:00"),
            "outTime": data.get("outTime", "17:00"),
            "phone": data.get("phone", ""),
            # Fee related fields
            "feeAmount": data.get("feeAmount", 2500),
            "feeDueDay": data.get("feeDueDay", 15),
            "feePaidForMonth": data.get("feePaidForMonth", None),
            "lastFeePaidDate": data.get("lastFeePaidDate", None),
            "created_at": datetime.now().isoformat()
        }
        
        save_student(student)
        return jsonify({"message": "Student added", "id": student["id"]}), 201
    
    # GET - Fetch all students
    all_students = get_all_students()
    return jsonify(all_students)


@app.route("/api/students/<student_id>", methods=["GET", "PUT", "DELETE"])
def student_actions(student_id):
    if request.method == "GET":
        all_students = get_all_students()
        student = next((s for s in all_students if s["id"] == student_id), None)
        if student:
            return jsonify(student)
        return jsonify({"error": "Student not found"}), 404
    
    if request.method == "PUT":
        data = request.json
        # Remove None values from update data
        update_data = {k: v for k, v in data.items() if v is not None}
        update_student(student_id, update_data)
        return jsonify({"message": "Student updated"})
    
    if request.method == "DELETE":
        # Delete student and all associated attendance records
        delete_student(student_id)
        # Delete associated attendance records
        all_attendance = get_all_attendance()
        for record in all_attendance:
            if record.get("studentId") == student_id:
                delete_attendance(record["id"])
        return jsonify({"message": "Student deleted"})


# ==================================================
# ATTENDANCE API
# ==================================================
@app.route("/api/attendance", methods=["GET", "POST"])
def attendance():
    if request.method == "POST":
        data = request.json
        records = data.get("attendance", [])
        now = datetime.now()
        today_date = now.strftime("%Y-%m-%d")
        
        saved_records = []
        for item in records:
            record_date = item.get("date", today_date)
            record_id = item.get("id", str(uuid.uuid4())[:8])
            
            record = {
                "id": record_id,
                "studentId": item["studentId"],
                "studentName": item["studentName"],
                "class": item.get("class", ""),
                "branch": item.get("branch", ""),
                "days": item.get("days", []),
                "status": item["status"],
                "inTime": item.get("inTime", "09:00"),
                "outTime": item.get("outTime", "17:00"),
                "date": record_date,
                "time": now.strftime("%H:%M:%S"),
                "timestamp": now.isoformat()
            }
            
            save_attendance(record)
            saved_records.append(record_id)
        
        return jsonify({"message": "Attendance saved", "records": saved_records}), 201
    
    # GET - Fetch all attendance records
    all_records = get_all_attendance()
    all_records.sort(key=lambda x: x.get("date", ""), reverse=True)
    return jsonify(all_records)


@app.route("/api/attendance/<record_id>", methods=["DELETE", "PUT"])
def attendance_actions(record_id):
    if request.method == "DELETE":
        try:
            delete_attendance(record_id)
            return jsonify({"message": "Attendance record deleted successfully"}), 200
        except Exception as e:
            print(f"Error deleting record: {str(e)}")
            return jsonify({"message": f"Error deleting record: {str(e)}"}), 500
    
    if request.method == "PUT":
        try:
            data = request.json
            
            update_data = {}
            if "status" in data:
                update_data["status"] = data["status"]
            if "inTime" in data:
                update_data["inTime"] = data["inTime"]
            if "outTime" in data:
                update_data["outTime"] = data["outTime"]
            if "date" in data:
                update_data["date"] = data["date"]
            
            update_data["updated_at"] = datetime.now().isoformat()
            update_attendance(record_id, update_data)
            
            return jsonify({"message": "Attendance updated successfully"}), 200
                
        except Exception as e:
            print(f"Error updating record: {str(e)}")
            return jsonify({"message": f"Error updating record: {str(e)}"}), 500


# ==================================================
# DASHBOARD STATS API
# ==================================================
@app.route("/api/stats", methods=["GET"])
def stats():
    today = datetime.now().strftime("%Y-%m-%d")
    
    total_students = count_documents("students")
    today_records = filter_attendance_by_date(today)
    total_records = count_documents("attendance")
    total_present = len(filter_attendance_by_status("Present"))
    
    # Calculate pending fees (students with overdue fee)
    all_students = get_all_students()
    overdue_count = 0
    total_pending_fees = 0
    
    for student in all_students:
        if student.get('feeAmount') and student.get('feeDueDay'):
            # Check if fee is overdue
            today_date = datetime.now()
            current_year = today_date.year
            current_month = today_date.month
            
            due_date = datetime(current_year, current_month, min(student['feeDueDay'], 28))
            if due_date < today_date and due_date.month == current_month:
                # If due date passed, next month's due date
                if current_month == 12:
                    due_date = datetime(current_year + 1, 1, min(student['feeDueDay'], 28))
                else:
                    due_date = datetime(current_year, current_month + 1, min(student['feeDueDay'], 28))
            
            paid_for = student.get('feePaidForMonth')
            current_month_str = f"{current_year}-{current_month}"
            
            if paid_for != current_month_str and due_date < today_date:
                overdue_count += 1
                total_pending_fees += student.get('feeAmount', 0)
    
    today_present = len([r for r in today_records if r.get("status") == "Present"])
    
    # Calculate today's attendance percentage
    today_percentage = 0
    if len(today_records) > 0:
        today_percentage = (today_present / len(today_records)) * 100
    
    return jsonify({
        "totalStudents": total_students,
        "todayTotal": len(today_records),
        "todayPresent": today_present,
        "todayPercentage": round(today_percentage, 1),
        "totalRecords": total_records,
        "totalPresent": total_present,
        "overdueCount": overdue_count,
        "totalPendingFees": total_pending_fees
    })


# ==================================================
# FEE MANAGEMENT API
# ==================================================
@app.route("/api/fee/status", methods=["GET"])
def fee_status():
    """Get fee status for all students"""
    all_students = get_all_students()
    today = datetime.now()
    current_month = f"{today.year}-{today.month}"
    
    result = []
    for student in all_students:
        # Check if overdue
        is_overdue = False
        days_overdue = 0
        
        if not student.get("feePaidForMonth") == current_month and student.get("feeDueDay"):
            due_date = datetime(today.year, today.month, min(student["feeDueDay"], 28))
            if due_date < today:
                is_overdue = True
                days_overdue = (today - due_date).days
        
        fee_status = {
            "id": student["id"],
            "name": student["name"],
            "branch": student.get("branch", ""),
            "class": student.get("class", ""),
            "phone": student.get("phone", ""),
            "feeAmount": student.get("feeAmount", 0),
            "feeDueDay": student.get("feeDueDay", 15),
            "paidForMonth": student.get("feePaidForMonth"),
            "lastPaidDate": student.get("lastFeePaidDate"),
            "isPaidForCurrentMonth": student.get("feePaidForMonth") == current_month,
            "isOverdue": is_overdue,
            "daysOverdue": days_overdue
        }
        
        result.append(fee_status)
    
    return jsonify(result)


@app.route("/api/fee/pay/<student_id>", methods=["POST"])
def mark_fee_paid(student_id):
    """Mark fee as paid for current month"""
    data = request.json
    today = datetime.now()
    current_month = f"{today.year}-{today.month}"
    
    update_data = {
        "feePaidForMonth": current_month,
        "lastFeePaidDate": today.isoformat(),
        "lastPaymentAmount": data.get("amount", 0)
    }
    
    update_student(student_id, update_data)
    return jsonify({"message": "Fee marked as paid successfully"})


# ==================================================
# EXPORT API
# ==================================================
@app.route("/api/export/attendance", methods=["GET"])
def export_attendance():
    """Export all attendance records as JSON"""
    records = get_all_attendance()
    return jsonify(records)


@app.route("/api/export/students", methods=["GET"])
def export_students():
    """Export all students as JSON"""
    students_list = get_all_students()
    return jsonify(students_list)


# ==================================================
# SEARCH API
# ==================================================
@app.route("/api/search/students", methods=["GET"])
def search_students():
    """Search students by name, branch, or class"""
    query = request.args.get("q", "").lower()
    
    all_students = get_all_students()
    
    if not query:
        return jsonify(all_students)
    
    # Filter students based on search query
    filtered = [s for s in all_students if 
                query in s.get("name", "").lower() or 
                query in s.get("branch", "").lower() or 
                query in s.get("class", "").lower()]
    
    return jsonify(filtered)


# ==================================================
# DEBUG AND UTILITY ROUTES
# ==================================================
@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    if students_col is not None:
        try:
            students_col.command("ping")
            return jsonify({"status": "healthy", "mongodb": "connected", "storage": "mongodb"})
        except:
            return jsonify({"status": "healthy", "mongodb": "disconnected", "storage": "in-memory"})
    else:
        return jsonify({"status": "healthy", "mongodb": "not_configured", "storage": "in-memory"})


@app.route("/api/clear/all", methods=["DELETE"])
def clear_all_data():
    """⚠️ DANGER: Clear all students and attendance records (for testing only)"""
    if request.args.get("confirm") != "YES":
        return jsonify({"error": "Use ?confirm=YES to confirm deletion"}), 400
    
    if students_col is not None:
        students_col.delete_many({})
        attendance_col.delete_many({})
    else:
        global in_memory_students, in_memory_attendance
        in_memory_students = []
        in_memory_attendance = []
    
    return jsonify({"message": "All data cleared successfully"})


# ==================================================
# RUN SERVER
# ==================================================
if __name__ == "__main__":
    # Create static folder if it doesn't exist
    if not os.path.exists("static"):
        os.makedirs("static")
        print("📁 Created 'static' folder - place your index.html here")
    
    print("\n" + "="*60)
    print("🚀 Subbulakshmi Venkatesan - Fee & Attendance Management System")
    print("="*60)
    print(f"📡 Server running at: http://localhost:5000")
    print(f"📁 Static files folder: ./static")
    if students_col is not None:
        print(f"💾 MongoDB: Connected to Atlas Cluster")
    else:
        print(f"💾 Storage: Using in-memory (no MongoDB connection)")
    print("="*60 + "\n")
    
    app.run(debug=True, host="0.0.0.0", port=5000)