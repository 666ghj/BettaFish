import os
import pandas as pd
from sqlalchemy import create_engine
from getpass import getpass
import logging

# ������־
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("save_data.log"),
        logging.StreamHandler()
    ]
)

# ���� articleAddr �� commentsAddr �Ǿ���·��������ڽű���·��
from spiderDataPackage.settings import articleAddr, commentsAddr

def get_db_connection_interactive():
    """
    ͨ���ն˽�����ȡ���ݿ����Ӳ����������س���ʹ��Ĭ��ֵ��
    ���� SQLAlchemy �����ݿ����档
    """
    print("�������������ݿ�������Ϣ��ֱ�Ӱ��س�ʹ��Ĭ��ֵ����")
    
    host = input(" 1. ���� (Ĭ��: localhost): ") or "localhost"
    port_str = input(" 2. �˿� (Ĭ��: 3306): ") or "3306"
    try:
        port = int(port_str)
    except ValueError:
        logging.warning("�˿ں���Ч��ʹ��Ĭ�϶˿� 3306��")
        port = 3306
    
    user = input(" 3. �û��� (Ĭ��: root): ") or "root"
    password = getpass(" 4. ���� (Ĭ��: 12345678): ") or "12345678"
    db_name = input(" 5. ���ݿ��� (Ĭ��: Weibo_PublicOpinion_AnalysisSystem): ") or "Weibo_PublicOpinion_AnalysisSystem"
    
    # �������ݿ������ַ���
    connection_str = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}?charset=utf8mb4"
    
    try:
        engine = create_engine(connection_str)
        # ��������
        with engine.connect() as connection:
            logging.info(f"�ɹ����ӵ����ݿ�: {user}@{host}:{port}/{db_name}")
        return engine
    except Exception as e:
        logging.error(f"�޷����ӵ����ݿ�: {e}")
        exit(1)

def saveData(engine):
    """
    �����ݿ��CSV�ļ���ȡ���ݣ��ϲ���ȥ�ز���������ݿ⡣
    ���ɾ��CSV�ļ���
    """
    try:
        # ��ȡ������
        oldArticle = pd.read_sql('SELECT * FROM article', engine)
        oldComment = pd.read_sql('SELECT * FROM comments', engine)
        logging.info("�ɹ������ݿ��ȡ�ɵ����º��������ݡ�")
        
        # ��ȡ������
        newArticle = pd.read_csv(articleAddr)
        newComment = pd.read_csv(commentsAddr)
        logging.info("�ɹ���CSV�ļ���ȡ�µ����º��������ݡ�")
        
        # �ϲ�����
        mergeArticle = pd.concat([newArticle, oldArticle], ignore_index=True, sort=False)
        mergeComment = pd.concat([newComment, oldComment], ignore_index=True, sort=False)
        logging.info("�ɹ��ϲ��¾����º��������ݡ�")
        
        # ȥ��
        mergeArticle.drop_duplicates(subset='id', keep='last', inplace=True)
        mergeComment.drop_duplicates(subset='content', keep='last', inplace=True)
        logging.info("�ɹ�ȥ���ظ������º��������ݡ�")
        
        # ��������ݿ�
        mergeArticle.to_sql('article', con=engine, if_exists='replace', index=False)
        mergeComment.to_sql('comments', con=engine, if_exists='replace', index=False)
        logging.info("�ɹ����ϲ�������ݱ�������ݿ⡣")
        
    except pd.errors.EmptyDataError as e:
        logging.error(f"��ȡCSV�ļ�ʱ����: {e}")
    except Exception as e:
        logging.error(f"��������ʱ����: {e}")
    else:
        # ɾ��CSV�ļ�
        try:
            os.remove(articleAddr)
            os.remove(commentsAddr)
            logging.info("�ɹ�ɾ��CSV�ļ���")
        except Exception as e:
            logging.warning(f"ɾ��CSV�ļ�ʱ����: {e}")

def main():
    # ��ȡ���ݿ�����
    engine = get_db_connection_interactive()
    
    # ��������
    saveData(engine)
    
    # �ر����棨��ѡ����ΪSQLAlchemy������Զ��������ӳأ�
    engine.dispose()
    logging.info("���ݿ������ѹرա�")

if __name__ == '__main__':
    main()
