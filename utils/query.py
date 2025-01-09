import getpass
import pymysql
import logging

# ������־
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("database_operations.log"),
        logging.StreamHandler()
    ]
)

def get_db_connection_interactive():
    """
    ͨ���ն˽�����ȡ���ݿ����Ӳ����������س���ʹ��Ĭ��ֵ��
    ����һ�����Ӷ���
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
    password = getpass.getpass(" 4. ���� (Ĭ��: 312517): ") or "312517"
    db_name = input(" 5. ���ݿ��� (Ĭ��: Weibo_PublicOpinion_AnalysisSystem): ") or "Weibo_PublicOpinion_AnalysisSystem"
    
    logging.info(f"�������ӵ����ݿ�: {user}@{host}:{port}/{db_name}")
    
    try:
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=db_name,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor  # �����ֵ��ʽ
        )
        logging.info("���ݿ����ӳɹ���")
        return connection
    except pymysql.MySQLError as e:
        logging.error(f"���ݿ�����ʧ��: {e}")
        exit(1)

# ��ȡ���ݿ�����
conn = get_db_connection_interactive()

# ��ȡ�α�
cursor = conn.cursor()

def query(sql, params=None, query_type="no_select"):
    """
    ִ��SQL��ѯ�������
    
    :param sql: SQL���
    :param params: SQL��������ѡ��
    :param query_type: ��ѯ���ͣ�Ĭ��Ϊ "no_select"
                       ������� "no_select"����ִ�� fetch ����
    :return: ����ǲ�ѯ���������������б����򷵻� None
    """
    try:
        if params:
            params = tuple(params)
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        
        # ȷ�����ӱ��ֻ�Ծ
        conn.ping(reconnect=True)
        
        if query_type != "no_select":
            data_list = cursor.fetchall()
            conn.commit()
            logging.info("��ѯ�ɹ����ѻ�ȡ���ݡ�")
            return data_list
        else:
            conn.commit()
            logging.info("�����ɹ������ύ����")
    except pymysql.MySQLError as e:
        logging.error(f"ִ��SQLʱ����: {e}")
        conn.rollback()
        return None

def main():
    # ʾ���÷�
    
    # ִ�в�ѯ����
    select_sql = "SELECT * FROM article LIMIT 5"
    articles = query(select_sql, query_type="select")
    if articles:
        for article in articles:
            print(article)
    
    # ִ�в������������ʵ�ʱ�ṹ�޸ģ�
    insert_sql = "INSERT INTO article (id, content) VALUES (%s, %s)"
    new_article = (12345, "����һ���µ��������ݡ�")
    result = query(insert_sql, params=new_article, query_type="no_select")
    if result is None:
        logging.info("���������ɡ�")
    
    # �ر��α������
    cursor.close()
    conn.close()
    logging.info("���ݿ������ѹرա�")

if __name__ == '__main__':
    main()
