import os
import json
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

class AIFitnessEngine:
    """
    A hybrid, production-grade AI Engine for personal health and fitness management.
    Uses OpenAI's Chat Completion API with JSON formatting if an API key is present.
    Falls back gracefully to a deterministic, rule-based expert system based on
    validated physiological equations (Mifflin-St Jeor, Activity Multipliers, and Split Routines)
    if the API key is not configured or fails.
    """

    def __init__(self):
        # Retrieve the API key from environment variables
        self.openai_key = os.environ.get("OPENAI_API_KEY", "")
        self.groq_key = os.environ.get("GROQ_API_KEY", "")
        
        if self.groq_key:
            # Use Groq API (fully compatible with OpenAI SDK)
            self.client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=self.groq_key
            )
            self.model_name = "llama-3.3-70b-versatile" 
        elif self.openai_key:
            # Use OpenAI API
            self.client = OpenAI(api_key=self.openai_key)
            self.model_name = "gpt-4o-mini"
        else:
            self.client = None
            self.model_name = None

    def generate_plans(self, profile: dict, logs: list = None, burnout_alert: bool = False, plateau_alert: bool = False) -> dict:
        """
        Generates customized 7-day workout and diet plans.
        :param profile: dict containing user physical metrics and goals.
            Expected structure:
            {
                "gender": "male" | "female" | "other",
                "age": int,
                "height": float (in cm),
                "weight": float (in kg),
                "activity_level": "sedentary" | "lightly_active" | "moderately_active" | "very_active",
                "fitness_goal": "weight_loss" | "muscle_gain" | "endurance" | "maintenance",
                "dietary_restrictions": list of str (e.g., ["vegan", "gluten_free"]),
                "medical_conditions": str (optional)
            }
        :param logs: list of recent activity logs (optional)
        :param burnout_alert: boolean indicating if burnout was detected
        :param plateau_alert: boolean indicating if a fitness plateau was detected
        :return: dict containing structured 'workout_plan' and 'diet_plan'
        """
        # Clean and sanitize input parameters
        profile = self._sanitize_profile(profile)

        # Try to use OpenAI if API key exists
        if self.client:
            try:
                return self._generate_via_openai(profile, logs, burnout_alert, plateau_alert)
            except Exception as e:
                logger.error(f"OpenAI generation failed: {str(e)}. Falling back to local expert system.")
                # If LLM fails, proceed to fallback system

        # Graceful fallback to deterministic physiological and training formulas
        return self._generate_via_expert_system(profile, logs, burnout_alert, plateau_alert)

    def _sanitize_profile(self, profile: dict) -> dict:
        """Fills missing keys in profile with safe defaults."""
        return {
            "gender": profile.get("gender", "other").lower(),
            "age": int(profile.get("age", 25)),
            "height": float(profile.get("height", 170.0)),
            "weight": float(profile.get("weight", 70.0)),
            "activity_level": profile.get("activity_level", "moderately_active").lower(),
            "fitness_goal": profile.get("fitness_goal", "maintenance").lower(),
            "dietary_restrictions": [r.lower().strip() for r in profile.get("dietary_restrictions", [])],
            "medical_conditions": profile.get("medical_conditions", "").strip()
        }

    def _generate_via_openai(self, profile: dict, logs: list, burnout_alert: bool, plateau_alert: bool) -> dict:
        """Calls OpenAI Chat Completion to generate structured JSON plans."""
        prompt = f"""
You are an expert AI Fitness Coach and Sports Dietitian. Generate a highly customized, scientifically optimal 7-day Workout Plan and a matching 7-day Diet Plan for a user with the following profile:
- Gender: {profile['gender']}
- Age: {profile['age']} years
- Height: {profile['height']} cm
- Weight: {profile['weight']} kg
- Activity Level: {profile['activity_level']}
- Fitness Goal: {profile['fitness_goal']}
- Dietary Restrictions: {', '.join(profile['dietary_restrictions']) if profile['dietary_restrictions'] else 'None'}
- Medical Conditions: {profile['medical_conditions'] if profile['medical_conditions'] else 'None'}

Context Flags:
- Burnout Detected: {burnout_alert} (If True, generate a Deload and Active Recovery Plan focusing on stretching, mobility, walking, and stress relief, keeping training volume low to allow recovery).
- Plateau Detected: {plateau_alert} (If True, adapt the plans to shock the body — cycle macros, introduce novel exercise variations, and alter sets/reps).

You MUST output your response in STRICT JSON format matching the following structural schema exactly:
{{
  "workout_plan": {{
    "title": "String (e.g. 'Hypertrophy Phase 1' or 'Active Recovery Deload')",
    "target_goal": "String",
    "weekly_sessions": [
      {{
        "day_of_week": "String (Monday, Tuesday, etc.)",
        "session_name": "String (e.g. 'Push Day' or 'Full Body Conditioning' or 'Rest & Recovery')",
        "exercises": [
          {{
            "name": "String",
            "sets": Integer,
            "reps": "String (e.g. '10-12' or '8')",
            "rest_time": "String (e.g. '90 seconds')",
            "order": Integer
          }}
        ]
      }}
    ]
  }},
  "diet_plan": {{
    "title": "String (e.g. 'High-Protein Caloric Deficit Plan')",
    "target_calories": Integer,
    "target_protein": Integer,
    "target_carbs": Integer,
    "target_fats": Integer,
    "meals": [
      {{
        "meal_time": "String (Breakfast, Lunch, Dinner, Snack)",
        "name": "String (e.g. 'Oatmeal with Chia Seeds')",
        "food_items": "String (ingredients summary)",
        "calories": Integer,
        "protein": Integer,
        "carbs": Integer,
        "fats": Integer
      }}
    ]
  }}
}}

Make sure the sum of meal calories approximately equals the target_calories, and macronutrient targets align with the daily caloric intake (1g Protein = 4 kcal, 1g Carb = 4 kcal, 1g Fat = 9 kcal). Include meals matching the user's dietary restrictions. Do not output any conversational text or markdown codeblocks, output only raw valid JSON.
"""
        response = self.client.chat.completions.create(
            model=self.model_name,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a professional fitness and diet planner returning structured JSON data."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        result_content = response.choices[0].message.content
        return json.loads(result_content)

    def _generate_via_expert_system(self, profile: dict, logs: list, burnout_alert: bool, plateau_alert: bool) -> dict:
        """
        A rule-based biological expert system calculating BMR, TDEE, macronutrient distributions,
        and structuring workout routines according to fitness guidelines.
        """
        # 1. Calculate BMR (Mifflin-St Jeor Equation)
        w, h, a = profile['weight'], profile['height'], profile['age']
        if profile['gender'] == 'male':
            bmr = 10 * w + 6.25 * h - 5 * a + 5
        elif profile['gender'] == 'female':
            bmr = 10 * w + 6.25 * h - 5 * a - 161
        else:
            bmr = 10 * w + 6.25 * h - 5 * a - 78 # Safe mid-point default

        # 2. Apply Activity Multipliers
        activity_multipliers = {
            "sedentary": 1.2,
            "lightly_active": 1.375,
            "moderately_active": 1.55,
            "very_active": 1.725
        }
        multiplier = activity_multipliers.get(profile['activity_level'], 1.55)
        tdee = bmr * multiplier

        # 3. Adjust Target Calories and Macros based on Goal, Burnout, and Plateau flags
        goal = profile['fitness_goal']
        
        if burnout_alert:
            # Focus on recovery: set calories to maintenance, low training intensity
            target_calories = int(tdee)
            diet_title = "Active Recovery & Restoration Fueling Plan"
            protein_ratio, fat_ratio, carb_ratio = 0.25, 0.25, 0.50 # High carbs for central nervous system recovery
        elif plateau_alert:
            # Dynamic macro shift to break plateau
            if goal == "weight_loss":
                target_calories = int(tdee - 600) # Slightly deeper deficit or shift
                protein_ratio, fat_ratio, carb_ratio = 0.40, 0.30, 0.30 # High protein/low carb shift
                diet_title = "Plateau-Breaker High-Protein Deficit Plan"
            elif goal == "muscle_gain":
                target_calories = int(tdee + 400) # Deeper surplus
                protein_ratio, fat_ratio, carb_ratio = 0.30, 0.25, 0.45 # Moderate carb cycling
                diet_title = "Plateau-Breaker Clean Hypertrophy Surplus Plan"
            else:
                target_calories = int(tdee)
                protein_ratio, fat_ratio, carb_ratio = 0.30, 0.30, 0.40
                diet_title = "Plateau-Breaker Metabolic Reset Plan"
        else:
            # Normal goal adjustments
            if goal == "weight_loss":
                target_calories = int(tdee - 500)
                protein_ratio, fat_ratio, carb_ratio = 0.35, 0.25, 0.40
                diet_title = "Lean Fat Loss Nutrition Plan"
            elif goal == "muscle_gain":
                target_calories = int(tdee + 300)
                protein_ratio, fat_ratio, carb_ratio = 0.25, 0.25, 0.50
                diet_title = "Optimal Muscle Building Surplus Plan"
            elif goal == "endurance":
                target_calories = int(tdee) # Maintenance with higher carbs
                protein_ratio, fat_ratio, carb_ratio = 0.20, 0.25, 0.55
                diet_title = "Aerobic Fueling Endurance Plan"
            else:
                target_calories = int(tdee)
                protein_ratio, fat_ratio, carb_ratio = 0.25, 0.25, 0.50
                diet_title = "Balanced Maintenance Nutrition Plan"

        # Safe boundaries (never drop below healthy biological floors)
        if target_calories < 1200:
            target_calories = 1200

        # Calculate exact macronutrients
        target_protein = int((target_calories * protein_ratio) / 4)
        target_fats = int((target_calories * fat_ratio) / 9)
        target_carbs = int((target_calories * carb_ratio) / 4)

        # 4. Generate Diet Meals according to Dietary Restrictions
        meals = self._generate_meals_for_diet(target_calories, target_protein, target_carbs, target_fats, profile['dietary_restrictions'])

        # 5. Generate Weekly Workout Sessions
        workout_plan = self._generate_workouts_for_routine(goal, burnout_alert, plateau_alert)

        return {
            "workout_plan": workout_plan,
            "diet_plan": {
                "title": diet_title,
                "target_calories": target_calories,
                "target_protein": target_protein,
                "target_carbs": target_carbs,
                "target_fats": target_fats,
                "meals": meals
            }
        }

    def _generate_meals_for_diet(self, calories: int, protein: int, carbs: int, fats: int, restrictions: list) -> list:
        """Assembles 4 cohesive daily meals adapted to calories and dietary restrictions."""
        is_vegan = "vegan" in restrictions
        is_vegetarian = "vegetarian" in restrictions or is_vegan
        is_gluten_free = "gluten_free" in restrictions or "gluten free" in restrictions
        is_keto = "keto" in restrictions

        # Baseline Meal Templates
        # Divide calories: Breakfast 25%, Lunch 35%, Dinner 30%, Snack 10%
        c_bf, c_lh, c_dn, c_sk = int(calories * 0.25), int(calories * 0.35), int(calories * 0.30), int(calories * 0.10)
        p_bf, p_lh, p_dn, p_sk = int(protein * 0.25), int(protein * 0.35), int(protein * 0.30), int(protein * 0.10)
        cb_bf, cb_lh, cb_dn, cb_sk = int(carbs * 0.25), int(carbs * 0.35), int(carbs * 0.30), int(carbs * 0.10)
        f_bf, f_lh, f_dn, f_sk = int(fats * 0.25), int(fats * 0.35), int(fats * 0.30), int(fats * 0.10)

        # 1. Breakfast Selection
        if is_keto:
            bf_name = "Keto Avocado and Eggs Scramble"
            bf_items = "3 Large Eggs, 1/2 Medium Avocado, 1 tbsp Olive Oil, Spinach, Mushrooms"
        elif is_vegan:
            bf_name = "High-Protein Vegan Berry Oatmeal"
            bf_items = f"45g Oats, 1 scoop Vegan Protein Powder, 120ml Soy Milk, 50g Blueberries, 1 tbsp Chia Seeds"
        elif is_vegetarian:
            bf_name = "Greek Yogurt and Honey Bowl"
            bf_items = "200g Non-fat Greek Yogurt, 1 tbsp Honey, 30g Almonds, 100g Sliced Strawberries"
        elif is_gluten_free:
            bf_name = "Gluten-Free Eggs & Sweet Potato Hash"
            bf_items = "2 Large Eggs, 100g Sweet Potato Cubes, Spinach, Sautéed with Coconut Oil"
        else:
            bf_name = "Classic Egg & Toast Breakfast"
            bf_items = "2 Whole Eggs, 2 Slices Whole Wheat Toast, 1 tsp Butter, 1 Medium Banana"

        # 2. Lunch Selection
        if is_keto:
            lh_name = "Keto Salmon & Asparagus Platter"
            lh_items = "150g Grilled Salmon, 100g Roasted Asparagus in Butter, Garden Salad with Olive Oil Dressing"
        elif is_vegan:
            lh_name = "Tofu Quinoa & Buddha Bowl"
            lh_items = "150g Firm Tofu, 80g Cooked Quinoa, Steamed Broccoli, Carrots, Tahini Dressing"
        elif is_vegetarian:
            lh_name = "Mediterranean Chickpea & Feta Salad"
            lh_items = "150g Chickpeas, 50g Feta Cheese, Cucumbers, Tomatoes, Olives, Vinaigrette Dressing"
        elif is_gluten_free:
            lh_name = "Grilled Chicken & Brown Rice Bowl"
            lh_items = "150g Grilled Chicken Breast, 100g Cooked Brown Rice, Sautéed Bell Peppers, Olive Oil"
        else:
            lh_name = "Turkey and Avocado Whole Wheat Wrap"
            lh_items = "1 Large Whole Wheat Tortilla, 120g Sliced Turkey Breast, 1/4 Avocado, Lettuce, Tomato, Mustard"

        # 3. Dinner Selection
        if is_keto:
            dn_name = "Keto Ribeye Steak & Cauliflower Mash"
            dn_items = "180g Ribeye Steak, 150g Cauliflower Puree with Heavy Cream, Sautéed Garlic Spinach"
        elif is_vegan:
            dn_name = "Hearty Lentil & Vegetable Stew"
            dn_items = "150g Cooked Brown Lentils, Zucchini, Tomatoes, Onions, 1 Slice Gluten-Free/Vegan Bread"
        elif is_vegetarian:
            dn_name = "Tempeh Stir-Fry with Jasmine Rice"
            dn_items = "150g Marinated Tempeh, Mixed Stir-fry Veggies (Snow peas, Peppers), 100g Cooked Jasmine Rice"
        elif is_gluten_free:
            dn_name = "Baked Salmon & Sweet Potato Mash"
            dn_items = "150g Baked Salmon, 120g Sweet Potato Mash, Roasted Green Beans in Olive Oil"
        else:
            dn_name = "Lean Beef Stir-Fry with Rice"
            dn_items = "150g Lean Ground Beef, 100g Cooked Brown Rice, Mixed Vegetables (Broccoli, Carrots), Soy Sauce"

        # 4. Snack Selection
        if is_keto:
            sk_name = "Keto Mixed Nut Mix"
            sk_items = "30g Macadamia Nuts, Pecans, and Walnuts"
        elif is_vegan:
            sk_name = "Hummus & Carrot Sticks"
            sk_items = "4 tbsp Garlic Hummus, 100g Baby Carrots, Cucumber Slices"
        elif is_vegetarian:
            sk_name = "Cottage Cheese & Pineapple Bowl"
            sk_items = "150g Low-fat Cottage Cheese, 50g Pineapple Chunks"
        elif is_gluten_free:
            sk_name = "Gluten-Free Rice Cakes & Peanut Butter"
            sk_items = "2 Plain Rice Cakes, 1.5 tbsp Creamy Peanut Butter"
        else:
            sk_name = "Protein Shake & Apple"
            sk_items = "1 Scoop Whey Protein, 250ml Skim Milk, 1 Medium Red Apple"

        return [
            {"meal_time": "Breakfast", "name": bf_name, "food_items": bf_items, "calories": c_bf, "protein": p_bf, "carbs": cb_bf, "fats": f_bf},
            {"meal_time": "Lunch", "name": lh_name, "food_items": lh_items, "calories": c_lh, "protein": p_lh, "carbs": cb_lh, "fats": f_lh},
            {"meal_time": "Dinner", "name": dn_name, "food_items": dn_items, "calories": c_dn, "protein": p_dn, "carbs": cb_dn, "fats": f_dn},
            {"meal_time": "Snack", "name": sk_name, "food_items": sk_items, "calories": c_sk, "protein": p_sk, "carbs": cb_sk, "fats": f_sk}
        ]

    def _generate_workouts_for_routine(self, goal: str, burnout_alert: bool, plateau_alert: bool) -> dict:
        """Assembles a full 7-day weekly training split adapted to goals and alert states."""
        
        if burnout_alert:
            # Deload, Stretch, Active Recovery
            title = "Active Recovery & Mobility Deload Phase"
            target_goal = "Nervous System Recovery & Active Rest"
            
            sessions = [
                {
                    "day_of_week": "Monday",
                    "session_name": "Full-Body Mobility & Yoga",
                    "exercises": [
                        {"name": "Dynamic Joint Warm-up", "sets": 1, "reps": "10 mins", "rest_time": "No rest", "order": 1},
                        {"name": "Vinyasa Flow Yoga (Low Intensity)", "sets": 1, "reps": "30 mins", "rest_time": "No rest", "order": 2},
                        {"name": "Child's Pose & Hamstring Stretch", "sets": 3, "reps": "45s hold", "rest_time": "30s", "order": 3}
                    ]
                },
                {
                    "day_of_week": "Tuesday",
                    "session_name": "Active Recovery Walk",
                    "exercises": [
                        {"name": "Outdoor Steady-State Walking (Zone 1)", "sets": 1, "reps": "40 mins", "rest_time": "No rest", "order": 1},
                        {"name": "Deep Breathing Exercises", "sets": 1, "reps": "5 mins", "rest_time": "No rest", "order": 2}
                    ]
                },
                {
                    "day_of_week": "Wednesday",
                    "session_name": "Rest Day",
                    "exercises": []
                },
                {
                    "day_of_week": "Thursday",
                    "session_name": "Foam Rolling & Deep Tissue Release",
                    "exercises": [
                        {"name": "Full Body Foam Rolling", "sets": 1, "reps": "20 mins", "rest_time": "No rest", "order": 1},
                        {"name": "Static Stretching Routine (Quads, Calves, Back)", "sets": 3, "reps": "30s hold", "rest_time": "15s", "order": 2}
                    ]
                },
                {
                    "day_of_week": "Friday",
                    "session_name": "Light Core & Joint Prehab",
                    "exercises": [
                        {"name": "Bird-Dog", "sets": 3, "reps": "10 per side", "rest_time": "45s", "order": 1},
                        {"name": "Glute Bridges (Bodyweight)", "sets": 3, "reps": "15", "rest_time": "45s", "order": 2},
                        {"name": "Plank", "sets": 3, "reps": "30-45s", "rest_time": "60s", "order": 3}
                    ]
                },
                {
                    "day_of_week": "Saturday",
                    "session_name": "Zone 2 Low-Intensity Cardio",
                    "exercises": [
                        {"name": "Stationary Cycling (Light Effort)", "sets": 1, "reps": "30 mins", "rest_time": "No rest", "order": 1}
                    ]
                },
                {
                    "day_of_week": "Sunday",
                    "session_name": "Complete Rest Day",
                    "exercises": []
                }
            ]

        elif plateau_alert:
            # Change exercises, set schemes, and add intensity techniques to break plateau
            title = "Plateau-Busting High-Intensity Shock Routine"
            target_goal = "Overcoming Physiological Stagnation"
            
            sessions = [
                {
                    "day_of_week": "Monday",
                    "session_name": "Push Day A (Plateau-Breaker: Rest-Pause Sets)",
                    "exercises": [
                        {"name": "Incline Dumbbell Press (Rest-Pause Technique)", "sets": 4, "reps": "8 + 3 + 2", "rest_time": "120s", "order": 1},
                        {"name": "Standing Overhead Press", "sets": 3, "reps": "6", "rest_time": "90s", "order": 2},
                        {"name": "Weighted Chest Dips", "sets": 3, "reps": "8-10", "rest_time": "90s", "order": 3},
                        {"name": "Cable Lateral Raise (Superset)", "sets": 4, "reps": "15", "rest_time": "No rest", "order": 4},
                        {"name": "Dumbbell Overhead Tricep Extension", "sets": 4, "reps": "12", "rest_time": "60s", "order": 5}
                    ]
                },
                {
                    "day_of_week": "Tuesday",
                    "session_name": "Pull Day A (Plateau-Breaker: Eccentric Overloads)",
                    "exercises": [
                        {"name": "Barbell Rows (5-second eccentric/lowering)", "sets": 4, "reps": "8", "rest_time": "90s", "order": 1},
                        {"name": "Weighted Pull-Ups", "sets": 3, "reps": "Max reps", "rest_time": "120s", "order": 2},
                        {"name": "Seated Cable Rows (Wide Grip)", "sets": 3, "reps": "12 (Drop set on last)", "rest_time": "90s", "order": 3},
                        {"name": "Face Pulls", "sets": 4, "reps": "15-20", "rest_time": "60s", "order": 4},
                        {"name": "Incline Dumbbell Bicep Curls", "sets": 3, "reps": "10-12", "rest_time": "60s", "order": 5}
                    ]
                },
                {
                    "day_of_week": "Wednesday",
                    "session_name": "Active Recovery & Mobility",
                    "exercises": [
                        {"name": "Foam Rolling & Deep Stretching", "sets": 1, "reps": "15 mins", "rest_time": "No rest", "order": 1}
                    ]
                },
                {
                    "day_of_week": "Thursday",
                    "session_name": "Leg Day (Plateau-Breaker: German Volume Training)",
                    "exercises": [
                        {"name": "Barbell Back Squats", "sets": 10, "reps": "10", "rest_time": "60s", "order": 1},
                        {"name": "Romanian Deadlifts", "sets": 4, "reps": "8", "rest_time": "90s", "order": 2},
                        {"name": "Leg Extensions (Superset)", "sets": 3, "reps": "15", "rest_time": "No rest", "order": 3},
                        {"name": "Seated Leg Curls", "sets": 3, "reps": "15", "rest_time": "60s", "order": 4},
                        {"name": "Standing Calf Raises", "sets": 4, "reps": "20", "rest_time": "45s", "order": 5}
                    ]
                },
                {
                    "day_of_week": "Friday",
                    "session_name": "Upper Body Power Split",
                    "exercises": [
                        {"name": "Flat Barbell Bench Press", "sets": 4, "reps": "5", "rest_time": "120s", "order": 1},
                        {"name": "Lat Pulldowns", "sets": 4, "reps": "8", "rest_time": "90s", "order": 2},
                        {"name": "Dumbbell Shoulder Press", "sets": 3, "reps": "8", "rest_time": "90s", "order": 3},
                        {"name": "Hammer Curls", "sets": 3, "reps": "12", "rest_time": "60s", "order": 4}
                    ]
                },
                {
                    "day_of_week": "Saturday",
                    "session_name": "HIIT Conditioning Cardiorespiratory Shock",
                    "exercises": [
                        {"name": "Sprinting Intervals (30s sprint, 60s walk)", "sets": 10, "reps": "15 mins total", "rest_time": "60s", "order": 1},
                        {"name": "Hanging Knee Raises", "sets": 3, "reps": "15", "rest_time": "45s", "order": 2}
                    ]
                },
                {
                    "day_of_week": "Sunday",
                    "session_name": "Rest Day",
                    "exercises": []
                }
            ]

        else:
            # Normal goal-based splits
            if goal == "weight_loss":
                title = "High-Intensity Full Body Metabolic Split"
                target_goal = "Caloric Expenditure & Lean Muscle Retention"
                
                sessions = [
                    {
                        "day_of_week": "Monday",
                        "session_name": "Full Body Resistance & Conditioning A",
                        "exercises": [
                            {"name": "Goblet Squats", "sets": 3, "reps": "12-15", "rest_time": "60s", "order": 1},
                            {"name": "Push-Ups (or Incline Pushups)", "sets": 3, "reps": "12-15", "rest_time": "60s", "order": 2},
                            {"name": "Dumbbell Rows", "sets": 3, "reps": "12-15", "rest_time": "60s", "order": 3},
                            {"name": "Kettlebell Swings", "sets": 4, "reps": "20", "rest_time": "60s", "order": 4},
                            {"name": "Plank with Shoulder Taps", "sets": 3, "reps": "45s", "rest_time": "45s", "order": 5}
                        ]
                    },
                    {
                        "day_of_week": "Tuesday",
                        "session_name": "Steady-State Cardio Zone 2",
                        "exercises": [
                            {"name": "Moderate Treadmill Incline Walk", "sets": 1, "reps": "45 mins", "rest_time": "No rest", "order": 1}
                        ]
                    },
                    {
                        "day_of_week": "Wednesday",
                        "session_name": "Full Body Resistance & Conditioning B",
                        "exercises": [
                            {"name": "Romanian Deadlifts", "sets": 3, "reps": "12", "rest_time": "60s", "order": 1},
                            {"name": "Seated Dumbbell Shoulder Press", "sets": 3, "reps": "12", "rest_time": "60s", "order": 2},
                            {"name": "Lat Pulldowns", "sets": 3, "reps": "12", "rest_time": "60s", "order": 3},
                            {"name": "Dumbbell Lunge Walk", "sets": 3, "reps": "10 per leg", "rest_time": "60s", "order": 4},
                            {"name": "Hanging Knee Raises", "sets": 3, "reps": "15", "rest_time": "45s", "order": 5}
                        ]
                    },
                    {
                        "day_of_week": "Thursday",
                        "session_name": "Rest & Mobility Day",
                        "exercises": [
                            {"name": "Full Body Static Stretching", "sets": 1, "reps": "15 mins", "rest_time": "No rest", "order": 1}
                        ]
                    },
                    {
                        "day_of_week": "Friday",
                        "session_name": "Full Body Resistance & Conditioning C",
                        "exercises": [
                            {"name": "Leg Press", "sets": 3, "reps": "15", "rest_time": "60s", "order": 1},
                            {"name": "Dumbbell Chest Flys", "sets": 3, "reps": "12", "rest_time": "60s", "order": 2},
                            {"name": "Face Pulls", "sets": 3, "reps": "15", "rest_time": "45s", "order": 3},
                            {"name": "Medicine Ball Slams", "sets": 4, "reps": "15", "rest_time": "45s", "order": 4},
                            {"name": "Bicycle Crunches", "sets": 3, "reps": "20 per side", "rest_time": "45s", "order": 5}
                        ]
                    },
                    {
                        "day_of_week": "Saturday",
                        "session_name": "Interval Cardio (HIIT)",
                        "exercises": [
                            {"name": "Elliptical HIIT Intervals (20s sprint, 40s moderate)", "sets": 15, "reps": "15 mins total", "rest_time": "40s", "order": 1}
                        ]
                    },
                    {
                        "day_of_week": "Sunday",
                        "session_name": "Complete Rest Day",
                        "exercises": []
                    }
                ]

            elif goal == "muscle_gain":
                title = "Hypertrophy Push-Pull-Legs Routine"
                target_goal = "Sarcoplasmic Muscle Hypertrophy & Strength"
                
                sessions = [
                    {
                        "day_of_week": "Monday",
                        "session_name": "Push Day (Chest, Shoulders, Triceps)",
                        "exercises": [
                            {"name": "Flat Dumbbell Bench Press", "sets": 4, "reps": "8-10", "rest_time": "90s", "order": 1},
                            {"name": "Seated Barbell Overhead Press", "sets": 3, "reps": "8-10", "rest_time": "90s", "order": 2},
                            {"name": "Incline Dumbbell Flys", "sets": 3, "reps": "10-12", "rest_time": "90s", "order": 3},
                            {"name": "Dumbbell Lateral Raises", "sets": 4, "reps": "12-15", "rest_time": "60s", "order": 4},
                            {"name": "Rope Tricep Pushdowns", "sets": 3, "reps": "12-15", "rest_time": "60s", "order": 5}
                        ]
                    },
                    {
                        "day_of_week": "Tuesday",
                        "session_name": "Pull Day (Back, Rear Delts, Biceps)",
                        "exercises": [
                            {"name": "Barbell Deadlifts", "sets": 3, "reps": "5", "rest_time": "120s", "order": 1},
                            {"name": "Lat Pulldowns (Wide Grip)", "sets": 4, "reps": "8-10", "rest_time": "90s", "order": 2},
                            {"name": "Seated Cable Rows", "sets": 3, "reps": "10-12", "rest_time": "90s", "order": 3},
                            {"name": "Face Pulls", "sets": 3, "reps": "15", "rest_time": "60s", "order": 4},
                            {"name": "Barbell Bicep Curls", "sets": 3, "reps": "10-12", "rest_time": "60s", "order": 5}
                        ]
                    },
                    {
                        "day_of_week": "Wednesday",
                        "session_name": "Rest Day",
                        "exercises": []
                    },
                    {
                        "day_of_week": "Thursday",
                        "session_name": "Leg Day (Quads, Hamstrings, Calves)",
                        "exercises": [
                            {"name": "Barbell Back Squats", "sets": 4, "reps": "6-8", "rest_time": "120s", "order": 1},
                            {"name": "Romanian Deadlifts", "sets": 4, "reps": "10", "rest_time": "90s", "order": 2},
                            {"name": "Dumbbell Bulgarian Split Squats", "sets": 3, "reps": "10 per leg", "rest_time": "90s", "order": 3},
                            {"name": "Seated Calf Raises", "sets": 4, "reps": "15", "rest_time": "60s", "order": 4}
                        ]
                    },
                    {
                        "day_of_week": "Friday",
                        "session_name": "Upper Body Hypertrophy Split",
                        "exercises": [
                            {"name": "Incline Barbell Chest Press", "sets": 4, "reps": "10", "rest_time": "90s", "order": 1},
                            {"name": "Single Arm Dumbbell Rows", "sets": 3, "reps": "10 per side", "rest_time": "90s", "order": 2},
                            {"name": "Dumbbell Arnold Press", "sets": 3, "reps": "10-12", "rest_time": "90s", "order": 3},
                            {"name": "Incline Dumbbell Curls (Superset)", "sets": 3, "reps": "12", "rest_time": "No rest", "order": 4},
                            {"name": "Dumbbell Hammer Curls", "sets": 3, "reps": "12", "rest_time": "60s", "order": 5}
                        ]
                    },
                    {
                        "day_of_week": "Saturday",
                        "session_name": "Active Recovery & Core Day",
                        "exercises": [
                            {"name": "Steady Outdoor Jogging", "sets": 1, "reps": "25 mins", "rest_time": "No rest", "order": 1},
                            {"name": "Hanging Leg Raises", "sets": 3, "reps": "12-15", "rest_time": "45s", "order": 2},
                            {"name": "Ab Wheel Rollouts", "sets": 3, "reps": "10", "rest_time": "60s", "order": 3}
                        ]
                    },
                    {
                        "day_of_week": "Sunday",
                        "session_name": "Complete Rest Day",
                        "exercises": []
                    }
                ]

            elif goal == "endurance":
                title = "Aerobic Base & Endurance Conditioning Plan"
                target_goal = "VO2 Max Improvement & Muscle Fatigue Resistance"
                
                sessions = [
                    {
                        "day_of_week": "Monday",
                        "session_name": "Tempo Aerobic Jogging",
                        "exercises": [
                            {"name": "Outdoor Jogging (Steady pace - Zone 3)", "sets": 1, "reps": "45 mins", "rest_time": "No rest", "order": 1}
                        ]
                    },
                    {
                        "day_of_week": "Tuesday",
                        "session_name": "High-Rep Muscle Endurance Circuit",
                        "exercises": [
                            {"name": "Bodyweight Squats", "sets": 3, "reps": "25", "rest_time": "30s", "order": 1},
                            {"name": "Dumbbell Shoulder Press (Light)", "sets": 3, "reps": "20", "rest_time": "30s", "order": 2},
                            {"name": "TRX/Cable Rows", "sets": 3, "reps": "20", "rest_time": "30s", "order": 3},
                            {"name": "Mountain Climbers", "sets": 3, "reps": "45 seconds", "rest_time": "30s", "order": 4},
                            {"name": "Plank Hold", "sets": 3, "reps": "60 seconds", "rest_time": "45s", "order": 5}
                        ]
                    },
                    {
                        "day_of_week": "Wednesday",
                        "session_name": "Active Recovery Cycling",
                        "exercises": [
                            {"name": "Light Stationary Cycling (Zone 1-2)", "sets": 1, "reps": "40 mins", "rest_time": "No rest", "order": 1}
                        ]
                    },
                    {
                        "day_of_week": "Thursday",
                        "session_name": "Interval Running (VO2 Max Builder)",
                        "exercises": [
                            {"name": "Running Warm-Up Pace", "sets": 1, "reps": "10 mins", "rest_time": "No rest", "order": 1},
                            {"name": "800m Repeats (Hard effort)", "sets": 5, "reps": "800 meters each", "rest_time": "3 mins jog rest", "order": 2},
                            {"name": "Running Cool-Down Stretch", "sets": 1, "reps": "10 mins", "rest_time": "No rest", "order": 3}
                        ]
                    },
                    {
                        "day_of_week": "Friday",
                        "session_name": "Core and Core Endurance",
                        "exercises": [
                            {"name": "Plank", "sets": 3, "reps": "60s", "rest_time": "45s", "order": 1},
                            {"name": "Side Plank", "sets": 3, "reps": "45s per side", "rest_time": "30s", "order": 2},
                            {"name": "Supermans", "sets": 3, "reps": "15", "rest_time": "45s", "order": 3}
                        ]
                    },
                    {
                        "day_of_week": "Saturday",
                        "session_name": "Long Slow Distance (LSD) Cardio",
                        "exercises": [
                            {"name": "Long Distance Cycling or Trail Run", "sets": 1, "reps": "75 mins (Zone 2)", "rest_time": "No rest", "order": 1}
                        ]
                    },
                    {
                        "day_of_week": "Sunday",
                        "session_name": "Complete Rest Day",
                        "exercises": []
                    }
                ]

            else:
                # Default Balanced Routine
                title = "Balanced Fitness Maintenance Routine"
                target_goal = "Overall Health, Strength & Cardiovascular Vitality"
                
                sessions = [
                    {
                        "day_of_week": "Monday",
                        "session_name": "Upper Body Balanced Day",
                        "exercises": [
                            {"name": "Dumbbell Bench Press", "sets": 3, "reps": "10", "rest_time": "90s", "order": 1},
                            {"name": "Seated Lat Pulldown", "sets": 3, "reps": "10", "rest_time": "90s", "order": 2},
                            {"name": "Overhead Dumbbell Press", "sets": 3, "reps": "10", "rest_time": "90s", "order": 3},
                            {"name": "Bicep Curls (Superset)", "sets": 3, "reps": "12", "rest_time": "No rest", "order": 4},
                            {"name": "Tricep Pushdowns", "sets": 3, "reps": "12", "rest_time": "60s", "order": 5}
                        ]
                    },
                    {
                        "day_of_week": "Tuesday",
                        "session_name": "Steady State Jogging",
                        "exercises": [
                            {"name": "Outdoor Jogging", "sets": 1, "reps": "30 mins", "rest_time": "No rest", "order": 1}
                        ]
                    },
                    {
                        "day_of_week": "Wednesday",
                        "session_name": "Lower Body Balanced Day",
                        "exercises": [
                            {"name": "Leg Press", "sets": 3, "reps": "10", "rest_time": "90s", "order": 1},
                            {"name": "Leg Curls", "sets": 3, "reps": "12", "rest_time": "60s", "order": 2},
                            {"name": "Goblet Squats", "sets": 3, "reps": "12", "rest_time": "90s", "order": 3},
                            {"name": "Standing Calf Raises", "sets": 3, "reps": "15", "rest_time": "45s", "order": 4}
                        ]
                    },
                    {
                        "day_of_week": "Thursday",
                        "session_name": "Rest Day",
                        "exercises": []
                    },
                    {
                        "day_of_week": "Friday",
                        "session_name": "Active Mobility & Yoga",
                        "exercises": [
                            {"name": "Vinyasa Yoga Flow", "sets": 1, "reps": "30 mins", "rest_time": "No rest", "order": 1}
                        ]
                    },
                    {
                        "day_of_week": "Saturday",
                        "session_name": "Light Cardio and Core",
                        "exercises": [
                            {"name": "Brisk Walking on Incline", "sets": 1, "reps": "30 mins", "rest_time": "No rest", "order": 1},
                            {"name": "Plank Hold", "sets": 3, "reps": "45s", "rest_time": "45s", "order": 2}
                        ]
                    },
                    {
                        "day_of_week": "Sunday",
                        "session_name": "Rest Day",
                        "exercises": []
                    }
                ]

        return {
            "title": title,
            "target_goal": target_goal,
            "weekly_sessions": sessions
        }


# --- CONVERSATIONAL AI ASSISTANT (used by /api/ai/chat/, separate from plan generation) ---

def get_ai_chat_reply(message: str, history: list = None) -> str:
    """
    Conversational counterpart to AIFitnessEngine.generate_plans — reuses the
    same Groq -> OpenAI -> fallback pattern, but for open-ended fitness Q&A
    instead of structured plan JSON.
    """
    engine = AIFitnessEngine()
    history = history or []

    if engine.client:
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are PulseFit AI, a friendly, knowledgeable fitness and nutrition "
                        "coach embedded in a fitness app. Give clear, encouraging, safe advice. "
                        "Keep responses concise (a few sentences to a short paragraph) unless the "
                        "user asks for more detail. Avoid medical diagnoses; suggest seeing a "
                        "doctor for medical concerns."
                    ),
                },
            ]
            for turn in history[-10:]:
                role = turn.get("role")
                content = turn.get("content")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": message})

            response = engine.client.chat.completions.create(
                model=engine.model_name,
                messages=messages,
                temperature=0.7,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"AI chat reply failed: {str(e)}. Falling back to canned response.")

    return _fallback_chat_reply(message)


def _fallback_chat_reply(message: str) -> str:
    """Deterministic, keyword-based reply used when no AI provider is
    configured or the API call fails — keeps the assistant usable offline."""
    text = message.lower()

    if any(word in text for word in ["burnout", "tired", "exhausted", "fatigue"]):
        return (
            "High fatigue for several days in a row is your body asking for a lighter week. "
            "Prioritize sleep, cut training volume by 30-50%, and keep moving with easy walks "
            "or mobility work instead of full rest days."
        )
    if any(word in text for word in ["plateau", "stuck", "not losing", "stalled"]):
        return (
            "Plateaus usually mean your body has adapted to your current calories or training "
            "stimulus. Try adjusting your calorie target by about 10%, or change up your rep "
            "ranges and exercise selection for 2-3 weeks."
        )
    if any(word in text for word in ["protein", "macro", "diet", "calorie", "nutrition"]):
        return (
            "As a rough guide, aim for 1.6-2.2g of protein per kg of bodyweight if you're "
            "training regularly, and build your calories around your goal (deficit for fat "
            "loss, surplus for muscle gain). Check your active diet plan on the Plans page for "
            "your personal targets."
        )
    if any(word in text for word in ["injury", "pain", "hurt", "doctor"]):
        return (
            "I can't diagnose pain or injuries. If something hurts beyond normal muscle "
            "soreness, please stop that movement and check in with a doctor or physiotherapist "
            "before continuing."
        )

    return (
        "I'm your PulseFit AI assistant. Ask me about your workout plan, nutrition targets, "
        "recovery, or anything about staying consistent with your fitness goals."
    )
