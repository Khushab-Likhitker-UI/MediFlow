import os
import random
import uuid
import datetime
import logging
from psycopg2.extras import execute_values, register_uuid
register_uuid()
from passlib.context import CryptContext
from dotenv import load_dotenv

# Import db connection manager
import db

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import bcrypt
_orig_hashpw = bcrypt.hashpw
bcrypt.hashpw = lambda s, salt: _orig_hashpw(s[:72], salt) if len(s) > 72 else _orig_hashpw(s, salt)
if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = type("About", (), {"__version__": getattr(bcrypt, "__version__", "4.0.0")})()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def seed_users():
    logger.info("Seeding Users...")
    users = [
        ("admin", "admin@smarthealth.local", "admin", hash_password("admin123"), True),
        ("manager_north", "manager1@smarthealth.local", "manager", hash_password("manager123"), True),
        ("viewer1", "viewer1@smarthealth.local", "viewer", hash_password("viewer123"), True),
    ]
    query = """
    INSERT INTO users (username, email, role, password_hash, is_active)
    VALUES %s ON CONFLICT (email) DO NOTHING
    """
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            execute_values(cur, query, users)
            conn.commit()

def seed_facilities():
    logger.info("Seeding Facilities (PHCs)...")
    facilities = [
        ("PHC-001", "Central District Hospital", "CHC", "North Block", "Karnataka", "Center Road", 12.9716, 77.5946),
        ("PHC-002", "Green Valley PHC", "PHC", "North Block", "Karnataka", "Valley Road", 12.9816, 77.5846),
        ("PHC-003", "Lakeview Clinic", "PHC", "South Block", "Karnataka", "Lake Edge", 12.9116, 77.6046),
        ("PHC-004", "Hilltop Health Center", "PHC", "East Block", "Karnataka", "Hill Area", 12.9516, 77.6546),
        ("PHC-005", "Riverside Medical", "PHC", "West Block", "Karnataka", "River Bend", 12.9616, 77.5246),
        ("PHC-006", "Sunrise Care", "PHC", "North Block", "Karnataka", "Sunrise Blvd", 12.9916, 77.5746),
        ("PHC-007", "Pine Grove Clinic", "PHC", "South Block", "Karnataka", "Pine Woods", 12.9216, 77.5846),
        ("PHC-008", "Maple Leaf Medical", "PHC", "East Block", "Karnataka", "Maple Street", 12.9616, 77.6646),
        ("PHC-009", "Oaktree Health", "PHC", "West Block", "Karnataka", "Oak Grove", 12.9416, 77.5146),
        ("PHC-010", "Willow Branch Clinic", "PHC", "North Block", "Karnataka", "Willow Creek", 12.9856, 77.5996),
    ]
    query = """
    INSERT INTO facilities (phc_id, facility_name, facility_type, district, state, address, latitude, longitude)
    VALUES %s ON CONFLICT (phc_id) DO NOTHING
    """
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            execute_values(cur, query, facilities)
            conn.commit()
    return [f[0] for f in facilities]

def seed_medicines():
    logger.info("Seeding Medicines...")
    medicines = [
        ("Paracetamol 500mg", "Paracetamol", "Medication", "tablets", 200, "PharmaCorp", "tablet"),
        ("Amoxicillin 250mg", "Amoxicillin", "Antibiotic", "capsules", 100, "BioMed", "capsule"),
        ("ORS Packets", "Oral Rehydration Salts", "Fluids", "sachets", 500, "HealthPlus", "powder"),
        ("Anti-venom", "Polyvalent Antivenom", "Emergency", "vials", 10, "Lifesciences", "injection"),
        ("IV Fluids", "Normal Saline 0.9%", "Fluids", "bags", 150, "Baxter", "solution"),
        ("Syringes", "5ml Syringe", "Consumables", "units", 600, "BD Medical", "other"),
        ("Bandages", "Gauze Bandage 2x2", "Consumables", "rolls", 100, "CareFirst", "other"),
        ("Ibuprofen 400mg", "Ibuprofen", "Medication", "tablets", 100, "PharmaCorp", "tablet"),
        ("N95 Respirator Mask", "N95 Mask", "PPE", "units", 200, "3M", "other"),
        ("Nitrile Exam Gloves", "Nitrile Gloves", "PPE", "boxes", 500, "Halyard Health", "other"),
        ("Azithromycin 500mg", "Azithromycin", "Antibiotic", "tablets", 150, "BioMed", "tablet"),
        ("Ciprofloxacin 500mg", "Ciprofloxacin", "Antibiotic", "tablets", 120, "PharmaCorp", "tablet"),
        ("Metformin 500mg", "Metformin", "Medication", "tablets", 300, "HealthPlus", "tablet"),
        ("Amlodipine 10mg", "Amlodipine", "Medication", "tablets", 250, "PharmaCorp", "tablet"),
        ("Insulin Glargine", "Insulin", "Medication", "vials", 50, "Lifesciences", "injection"),
        ("Omeprazole 20mg", "Omeprazole", "Medication", "capsules", 200, "BioMed", "capsule"),
        ("Cetirizine 10mg", "Cetirizine", "Medication", "tablets", 350, "HealthPlus", "tablet"),
        ("Losartan 50mg", "Losartan", "Medication", "tablets", 180, "PharmaCorp", "tablet"),
        ("Atorvastatin 20mg", "Atorvastatin", "Medication", "tablets", 220, "BioMed", "tablet"),
        ("Albuterol Inhaler", "Albuterol", "Respiratory", "units", 80, "Baxter", "inhaler"),
        ("Ceftriaxone 1g", "Ceftriaxone", "Antibiotic", "vials", 60, "Lifesciences", "injection"),
        ("Morphine 10mg", "Morphine", "Pain Relief", "vials", 30, "PharmaCorp", "injection"),
        ("Dexamethasone 4mg", "Dexamethasone", "Steroid", "tablets", 150, "BioMed", "tablet"),
        ("Epinephrine Auto-injector", "Epinephrine", "Emergency", "units", 20, "Lifesciences", "injection"),
        ("Hydrocortisone Cream", "Hydrocortisone", "Topical", "tubes", 90, "CareFirst", "cream"),
    ]
    query = """
    INSERT INTO medicines (name, generic_name, category, unit, reorder_level, supplier, dosage_form)
    VALUES %s ON CONFLICT (name) DO NOTHING
    RETURNING item_id, name
    """
    med_ids = {}
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            execute_values(cur, query, medicines, fetch=True)
            results = cur.fetchall()
            for r in results:
                med_ids[r[1]] = r[0]
            
            # Fallback if records already existed due to ON CONFLICT DO NOTHING
            if not med_ids or len(med_ids) < len(medicines):
                cur.execute("SELECT item_id, name FROM medicines")
                for r in cur.fetchall():
                    med_ids[r[1]] = r[0]
                    
            conn.commit()
    return med_ids

def seed_inventory(phc_list, med_ids):
    logger.info("Seeding Inventory & Inventory Transactions...")
    inventory = []
    transactions = []
    today = datetime.date.today()
    
    for idx, phc in enumerate(phc_list):
        for name, item_id in med_ids.items():
            # Create deterministic shortages and surpluses across PHCs so Sankey graph lights up!
            # Every 3rd PHC has critical shortage for items, every 4th has high surplus
            if (idx + item_id) % 3 == 0:
                qty = random.randint(5, 40)  # Critical shortage (< 48h stock)
            elif (idx + item_id) % 4 == 0:
                qty = random.randint(3000, 8000)  # Surplus (> 150% stock)
            else:
                qty = random.randint(200, 1500)  # Healthy stock

            batch = f"BATCH-{random.randint(1000, 9999)}"
            expiry = today + datetime.timedelta(days=random.randint(90, 700))
            offline_sync = str(uuid.uuid4())
            
            inventory.append((phc, item_id, batch, qty, expiry, offline_sync))
            transactions.append((phc, item_id, batch, 'received', qty, uuid.uuid4(), 'Initial Stock', None, offline_sync))

    # Bulk insert inventory
    inv_query = """
    INSERT INTO inventory (phc_id, item_id, batch_number, quantity, expiry_date, offline_sync_id)
    VALUES %s ON CONFLICT (phc_id, item_id, batch_number) DO NOTHING
    """
    txn_query = """
    INSERT INTO inventory_transactions (phc_id, item_id, batch_number, transaction_type, quantity, reference_id, remarks, performed_by, offline_sync_id)
    VALUES %s
    """
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            execute_values(cur, inv_query, inventory)
            execute_values(cur, txn_query, transactions)
            conn.commit()

def seed_historical_consumption(phc_list, med_ids):
    logger.info("Seeding Historical Medicine Consumption & Footfall (6 months)...")
    consumption = []
    footfall = []
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=180)

    for phc in phc_list:
        current_date = start_date
        while current_date <= end_date:
            # Base footfall pattern (sine wave to simulate seasonality + random noise)
            day_of_week = current_date.weekday()
            base_footfall = int(120 + 30 * random.random() + (50 if day_of_week < 5 else 10))
            footfall.append((phc, current_date, base_footfall))

            for name, item_id in med_ids.items():
                if "Anti-venom" in name:
                    qty_consumed = random.choices([0, 1, 2, 5], weights=[0.8, 0.1, 0.05, 0.05])[0]
                    # Outbreak simulation in one particular month
                    if current_date.month == 5 and phc in ["PHC-002", "PHC-006"]:
                        qty_consumed = random.randint(5, 15)
                else:
                    qty_consumed = int(base_footfall * random.uniform(0.1, 1.5))
                
                patients = int(qty_consumed * random.uniform(0.8, 1.0))
                consumption.append((phc, item_id, current_date, qty_consumed, patients, str(uuid.uuid4())))
            
            current_date += datetime.timedelta(days=1)

    footfall_query = """
    INSERT INTO daily_footfall (phc_id, date, patient_count)
    VALUES %s ON CONFLICT (phc_id, date) DO NOTHING
    """
    consumption_query = """
    INSERT INTO medicine_consumption (phc_id, item_id, consumption_date, quantity_consumed, patients_served, offline_sync_id)
    VALUES %s ON CONFLICT (phc_id, item_id, consumption_date) DO NOTHING
    """
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            execute_values(cur, footfall_query, footfall)
            execute_values(cur, consumption_query, consumption) 
            conn.commit()

def seed_personnel_and_attendance(phc_list):
    logger.info("Seeding Personnel & Attendance (Both PHC-level and individual level)...")
    personnel = []
    
    roles = ['doctor', 'nurse', 'pharmacist', 'lab_technician']
    today = datetime.date.today()
    
    # 1. First insert all personnel
    for phc in phc_list:
        for i in range(random.randint(5, 15)):
            personnel.append((
                phc, f"FName{i}", f"LName{i}", random.choice(roles),
                f"+91-98765432{random.randint(10,99)}-{uuid.uuid4().hex[:4]}", # Ensured unique
                f"staff{i}_{phc.lower()}_{uuid.uuid4().hex[:4]}@phc.local",
                today - datetime.timedelta(days=random.randint(100, 1000))
            ))

    p_query = """
    INSERT INTO personnel (phc_id, first_name, last_name, role, contact_number, email, joining_date)
    VALUES %s ON CONFLICT (contact_number) DO NOTHING
    RETURNING personnel_id, phc_id, role
    """
    inserted_personnel = []
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            execute_values(cur, p_query, personnel, fetch=True)
            inserted_personnel = cur.fetchall()
            
            # Fallback if personnel already existed
            if not inserted_personnel:
                cur.execute("SELECT personnel_id, phc_id, role FROM personnel")
                inserted_personnel = cur.fetchall()
                
            conn.commit()

    if not inserted_personnel:
        return

    # 2. Iterate and build attendance structure
    phc_attendance_summary = []
    personnel_attendance = []
    
    # Organize personnel by PHC ID
    phc_staff_map = {phc: [] for phc in phc_list}
    for person in inserted_personnel:
        phc_id = person[1]
        role = person[2]
        if phc_id in phc_staff_map:
            phc_staff_map[phc_id].append((person[0], role)) # pid, role
    
    for phc in phc_list:
        staff_pool = phc_staff_map.get(phc, [])
        for i in range(30):
            d = today - datetime.timedelta(days=i)
            doctors_present = 0
            for (pid, role) in staff_pool:
                # 80% chance present
                if random.random() < 0.8:
                    personnel_attendance.append((pid, phc, d, 'present', str(uuid.uuid4())))
                    if role == 'doctor':
                        doctors_present += 1
                else:
                    personnel_attendance.append((pid, phc, d, 'absent', str(uuid.uuid4())))
                    
            phc_attendance_summary.append((phc, d, doctors_present, str(uuid.uuid4())))

    pa_query = """
    INSERT INTO personnel_attendance (personnel_id, phc_id, attendance_date, attendance_status, offline_sync_id)
    VALUES %s ON CONFLICT (personnel_id, attendance_date) DO NOTHING
    """
    phc_a_query = """
    INSERT INTO phc_attendance_summary (phc_id, attendance_date, doctors_present, offline_sync_id)
    VALUES %s ON CONFLICT (phc_id, attendance_date) DO NOTHING
    """
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            execute_values(cur, pa_query, personnel_attendance)
            execute_values(cur, phc_a_query, phc_attendance_summary)
            conn.commit()

def seed_beds(phc_list):
    logger.info("Seeding Beds Capacity...")
    beds = []
    for phc in phc_list:
        total = random.randint(20, 50)
        occupied = random.randint(5, total - 5)
        avail = total - occupied
        beds.append((phc, avail, str(uuid.uuid4())))

    query = """
    INSERT INTO beds (phc_id, available_beds, offline_sync_id)
    VALUES %s ON CONFLICT (phc_id) DO NOTHING
    """
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            execute_values(cur, query, beds)
            conn.commit()

def run_all():
    try:
        logging.info("Starting Seed Generation")
        seed_users()
        phc_list = seed_facilities()
        med_ids = seed_medicines()
        
        # Only continue if medicines actually got inserted/fetched properly
        if med_ids:
            seed_inventory(phc_list, med_ids)
            seed_historical_consumption(phc_list, med_ids)
            seed_personnel_and_attendance(phc_list)
            seed_beds(phc_list)
            
            logging.info("Seed successful! Minimal production-quality database populated.")
        else:
            logging.warning("No medicines fetched. Did you run the schema first?")
            
    except Exception as e:
        logger.error(f"Seeding failed: {e}")

if __name__ == "__main__":
    run_all()
