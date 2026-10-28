import cv2
import face_recognition
import numpy as np
import os
import base64
import threading
import time
import datetime
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.files.base import ContentFile
from .models import RegisteredFace


def dashboard(request):
    return render(request, 'dashboard/dashboard.html')


@csrf_exempt
def register_face(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        image_data = request.POST.get('image', '')

        if not name:
            return JsonResponse({'success': False, 'message': 'Name is required.'})
        if not image_data:
            return JsonResponse({'success': False, 'message': 'No image provided.'})

        try:
            print("\n" + "="*60)
            print(" FACE REGISTRATION PIPELINE")
            print("="*60)

            header, encoded = image_data.split(',', 1)
            image_bytes = base64.b64decode(encoded)
            np_array = np.frombuffer(image_bytes, dtype=np.uint8)
            frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            h, w = frame.shape[:2]
            print(f"[1/3] Image received     : {w}x{h} pixels")
            print(f"[2/3] Face detection     : Scanning...")

            start = time.time()
            face_locations = face_recognition.face_locations(rgb_frame, model="hog")
            detect_time = time.time() - start

            if not face_locations:
                print("      Result           : No face detected")
                print("="*60 + "\n")
                return JsonResponse({'success': False, 'message': 'No face detected. Please try again.'})

            top, right, bottom, left = face_locations[0]
            print(f"      Faces found      : {len(face_locations)}")
            print(f"      Location         : top={top} right={right} bottom={bottom} left={left}")
            print(f"      Detection time   : {detect_time:.3f}s")

            print(f"[3/3] Encoding           : Extracting 128-point vector...")
            start = time.time()
            encoding = face_recognition.face_encodings(rgb_frame, face_locations)[0]
            encode_time = time.time() - start

            sample_str = ', '.join([f"{v:.3f}" for v in encoding[:5]])
            print(f"      Vector sample    : [{sample_str} ...]")
            print(f"      Encoding time    : {encode_time:.3f}s")

            existing = RegisteredFace.objects.all()
            if existing.exists():
                print(f"\n      Uniqueness check : Comparing against {existing.count()} registered face(s)...")
                for ef in existing:
                    ex_enc = ef.get_encoding()
                    distance = float(np.linalg.norm(encoding - ex_enc))
                    status = "possible duplicate" if distance < 0.50 else "different"
                    print(f"      vs {ef.name:<15} : distance = {distance:.4f} ({status})")

            face = RegisteredFace(name=name)
            face.set_encoding(encoding)
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{name.replace(' ', '_')}_{timestamp}.jpg"
            face.image.save(filename, ContentFile(image_bytes), save=False)
            face.save()

            total = RegisteredFace.objects.count()
            print(f"\n      Assigned ID      : #{face.pk} — {name}")
            print(f"      Total indexed    : {total} face(s)")
            print(f"      Image saved      : media/registered_faces/{filename}")
            print("="*60)
            print(f" REGISTERED SUCCESSFULLY: {name}")
            print("="*60 + "\n")

            FaceIndex.rebuild()

            return JsonResponse({'success': True, 'message': f'"{name}" registered successfully!'})

        except Exception as e:
            print(f"[ERROR] Registration failed: {str(e)}")
            print("="*60 + "\n")
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})

    return JsonResponse({'success': False, 'message': 'Invalid request.'})


@csrf_exempt
def detect_frame(request):
    if request.method == 'POST':
        try:
            image_data = request.POST.get('image', '')
            if not image_data:
                return JsonResponse({'faces': []})

            header, encoded = image_data.split(',', 1)
            image_bytes = base64.b64decode(encoded)
            np_array = np.frombuffer(image_bytes, dtype=np.uint8)
            frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Resize for speed
            small = cv2.resize(rgb_frame, (0, 0), fx=0.25, fy=0.25)

            face_locations = face_recognition.face_locations(small, model="hog")
            face_encodings = face_recognition.face_encodings(small, face_locations)

            if not FaceIndex._built:
                FaceIndex.rebuild()

            detected = []
            for (top, right, bottom, left), enc in zip(face_locations, face_encodings):
                name, fid, confidence, results = FaceIndex.search(enc)

                # Log every detection
                print(f"[DETECT] Frame received")
                print(f"         Faces found  : {len(face_locations)}")
                for fid_r, name_r, dist_r in results:
                    marker = "✓" if name_r == name and name != "Unknown" else " "
                    print(f"         ID #{fid_r} {name_r:<12} : distance = {dist_r:.4f} {marker}")
                if name != "Unknown":
                    print(f"[MATCH]  Result       : {name} (confidence {confidence}%)")
                else:
                    print(f"[MATCH]  Result       : Unknown")

                detected.append({
                    'top': top * 4,
                    'right': right * 4,
                    'bottom': bottom * 4,
                    'left': left * 4,
                    'name': name,
                    'confidence': confidence
                })

            return JsonResponse({'faces': detected})

        except Exception as e:
            print(f"[DETECT ERROR] {str(e)}")
            return JsonResponse({'faces': []})

    return JsonResponse({'faces': []})


def registered_faces(request):
    faces = RegisteredFace.objects.all()
    names = list(set(f.name for f in faces))
    return JsonResponse({'faces': names, 'total': faces.count()})


# ============================================================
#  FACE INDEX — vector cache
# ============================================================

class FaceIndex:
    _encodings = []
    _names = []
    _ids = []
    _lock = threading.Lock()
    _built = False

    @classmethod
    def rebuild(cls):
        with cls._lock:
            faces = RegisteredFace.objects.all()
            cls._encodings = []
            cls._names = []
            cls._ids = []
            for f in faces:
                cls._encodings.append(f.get_encoding())
                cls._names.append(f.name)
                cls._ids.append(f.pk)
            cls._built = True
            print(f"\n[INDEX] Rebuilt — {len(cls._encodings)} face(s) loaded into memory\n")

    @classmethod
    def search(cls, encoding, threshold=0.50):
        with cls._lock:
            if not cls._encodings:
                return "Unknown", None, None, []

            enc_matrix = np.array(cls._encodings)
            distances = np.linalg.norm(enc_matrix - encoding, axis=1)

            results = []
            for i, (dist, name, fid) in enumerate(zip(distances, cls._names, cls._ids)):
                results.append((fid, name, float(dist)))

            best_idx = np.argmin(distances)
            best_dist = float(distances[best_idx])
            best_name = cls._names[best_idx]
            best_id = cls._ids[best_idx]

            if best_dist < threshold:
                confidence = round((1 - best_dist) * 100, 1)
                return best_name, best_id, confidence, results
            else:
                return "Unknown", None, None, results


# Pre-build index on server start
FaceIndex.rebuild()