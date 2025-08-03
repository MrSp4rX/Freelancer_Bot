# To be placed in: freelancer_bot/populate_skills.py

from database import SessionLocal, Skill

def populate_skills():
    """Adds a predefined list of skills to the database if they don't already exist."""
    
    db_session = SessionLocal()
    
    skill_list = [
        # Development & Engineering
        {'name': 'Python Development', 'category': 'Development & Engineering'},
        {'name': 'JavaScript Development', 'category': 'Development & Engineering'},
        {'name': 'React / Next.js', 'category': 'Development & Engineering'},
        {'name': 'Node.js Development', 'category': 'Development & Engineering'},
        {'name': 'Full-Stack Development', 'category': 'Development & Engineering'},
        {'name': 'Telegram Bot Development', 'category': 'Development & Engineering'},
        {'name': 'Mobile App Development (iOS/Android)', 'category': 'Development & Engineering'},
        {'name': 'Software Development', 'category': 'Development & Engineering'},
        {'name': 'Web Development', 'category': 'Development & Engineering'},
        {'name': 'Ethical Hacking', 'category': 'Development & Engineering'},
        {'name': 'Smart Contract Development', 'category': 'Development & Engineering'},
        {'name': 'Blockchain & Web3', 'category': 'Development & Engineering'},
        {'name': 'Game Development', 'category': 'Development & Engineering'},
        {'name': 'Go (Golang) Development', 'category': 'Development & Engineering'},

        # AI & Data Science
        {'name': 'AI/ML Engineering', 'category': 'AI & Data Science'},
        {'name': 'Data Analysis', 'category': 'AI & Data Science'},
        {'name': 'Data Engineering', 'category': 'AI & Data Science'},
        {'name': 'Data Science', 'category': 'AI & Data Science'},
        {'name': 'Generative AI', 'category': 'AI & Data Science'},
        {'name': 'Machine Learning', 'category': 'AI & Data Science'},
        {'name': 'Prompt Engineering', 'category': 'AI & Data Science'},
        {'name': 'Data Visualization', 'category': 'AI & Data Science'},
        {'name': 'Natural Language Processing (NLP)', 'category': 'AI & Data Science'},

        # Cloud & DevOps
        {'name': 'Cloud Computing (AWS/Azure/GCP)', 'category': 'Cloud & DevOps'},
        {'name': 'Cloud Architecture', 'category': 'Cloud & DevOps'},
        {'name': 'DevOps Engineering', 'category': 'Cloud & DevOps'},
        {'name': 'Containerization (Docker/Kubernetes)', 'category': 'Cloud & DevOps'},
        {'name': 'CI/CD Implementation', 'category': 'Cloud & DevOps'},
        {'name': 'Infrastructure as Code (IaC)', 'category': 'Cloud & DevOps'},

        # Cybersecurity
        {'name': 'Cybersecurity Analysis', 'category': 'Cybersecurity'},
        {'name': 'Network Security', 'category': 'Cybersecurity'},
        {'name': 'Cloud Security', 'category': 'Cybersecurity'},
        {'name': 'Incident Response', 'category': 'Cybersecurity'},

        # Design & Product
        {'name': 'UI/UX Design', 'category': 'Design & Product'},
        {'name': 'Graphic Design', 'category': 'Design & Product'},
        {'name': 'Product Management', 'category': 'Design & Product'},
        {'name': 'User Research', 'category': 'Design & Product'},
        {'name': 'AR/VR Development', 'category': 'Design & Product'},
        {'name': 'Motion Graphics', 'category': 'Design & Product'},
        
        # Writing & Marketing
        {'name': 'Copywriting', 'category': 'Writing & Marketing'},
        {'name': 'Content Creation', 'category': 'Writing & Marketing'},
        {'name': 'Digital Marketing', 'category': 'Writing & Marketing'},
        {'name': 'SEO Specialist', 'category': 'Writing & Marketing'},
        {'name': 'Social Media Marketing', 'category': 'Writing & Marketing'},
        {'name': 'Technical Writing', 'category': 'Writing & Marketing'},
        {'name': 'Ad Campaign Management', 'category': 'Writing & Marketing'},

        # Admin & Business Support
        {'name': 'Project Management', 'category': 'Admin & Business Support'},
        {'name': 'Virtual Assistant', 'category': 'Admin & Business Support'},
        {'name': 'Community Management', 'category': 'Admin & Business Support'},
        {'name': 'Customer Support', 'category': 'Admin & Business Support'},
        {'name': 'Translation', 'category': 'Admin & Business Support'},
        {'name': 'Business Analysis', 'category': 'Admin & Business Support'},
        {'name': 'Financial Management', 'category': 'Admin & Business Support'},
    ]
    
    print("Populating skills...")
    
    try:
        for skill_data in skill_list:
            # Check if the skill already exists
            exists = db_session.query(Skill).filter(Skill.name == skill_data['name']).first()
            if not exists:
                new_skill = Skill(name=skill_data['name'], category=skill_data['category'])
                db_session.add(new_skill)
                print(f"  - Added '{skill_data['name']}' under '{skill_data['category']}'")
        
        db_session.commit()
        print("Skills populated successfully.")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        db_session.rollback()
        
    finally:
        db_session.close()

if __name__ == '__main__':
    populate_skills()


