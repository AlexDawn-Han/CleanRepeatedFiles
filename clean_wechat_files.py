import os
import hashlib
from tqdm import tqdm
import stat
import sys
import getpass
import socket
from datetime import datetime

def get_file_hash(filepath):
    """计算文件的 SHA256 哈希值"""
    hash_sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        print(f"[错误] 无法读取文件 {filepath}: {e}")
        return None

# === 新增：记录删除日志 ===
def log_deletion(file_path):
    try:
        hostname = socket.gethostname()  # 获取设备名
        username = getpass.getuser()    # 获取当前用户名
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_entry = f"[{timestamp}] 用户: {username} @ 设备: {hostname} | 删除文件: {file_path}\n"
        
        with open("deletion_log.txt", "a", encoding="utf-8") as log_file:
            log_file.write(log_entry)
    except Exception as e:
        print(f"[警告] 日志记录失败: {e}")

def delete_file(file_path):
    """尝试删除文件，如果失败则尝试强制删除"""
    try:
        os.remove(file_path)
        log_deletion(file_path)  # <<< 新增：记录删除日志
        return True
    except PermissionError:
        print(f"[提示] 权限不足，尝试强制删除：{file_path}")
        try:
            os.chmod(file_path, stat.S_IWRITE)
            os.remove(file_path)
            log_deletion(file_path)  # <<< 新增：记录删除日志
            return True
        except Exception as e:
            print(f"[失败] 无法删除文件 {file_path}：{e}")
            return False
    except Exception as e:
        print(f"[失败] 未知错误：{file_path} - {e}")
        return False

def is_duplicate_indicator_in_filename(filename):
    duplicate_indicators = ['(1)', '副本', 'copy', '(2)', '(副本)', '_副本']
    return any(indicator in filename.lower() for indicator in duplicate_indicators)

def main():
    print("=== 重复文件清理工具(支持WeChat收件夹) ===\n")

    folder = input("请输入要扫描的文件夹路径: ").strip()
    if not os.path.isdir(folder):
        print("[错误] 路径无效或不存在，请检查后重试。")
        return

    print(f"\n[选择] 已选择路径：{folder}\n")

    # 第一步：遍历目录，获取所有文件
    files = []
    print("[扫描] 正在收集所有文件...")
    for root_dir, _, filenames in os.walk(folder):
        for name in filenames:
            full_path = os.path.join(root_dir, name)
            files.append(full_path)

    total_files = len(files)
    print(f"[完成] 共找到 {total_files} 个文件。\n")
    print("\n📌 提示：")
    print("1. 请确保目标文件夹没有被其他程序占用。")
    print("2. 强烈建议先手动备份重要文件。")
    print("3. 程序通过计算===哈希值===判断重复，与文件名无关")
    print("4. 程序会优先删除文件名中带有 '(1)' 或'-副本'的副本。\n")
    print("5. 删除文件有风险，文件丢失概不负责")

    # 第二步：计算哈希并分组
    hash_dict = {}
    print("[计算] 正在计算文件哈希值（SHA256）...\n")
    for file in tqdm(files, desc="计算哈希", unit="files"):
        h = get_file_hash(file)
        if h:
            if h not in hash_dict:
                hash_dict[h] = []
            hash_dict[h].append(file)

    # 第三步：找出重复项
    duplicates = {k: v for k, v in hash_dict.items() if len(v) > 1}
    total_duplicates = sum(len(files_list) - 1 for files_list in duplicates.values())

    if total_duplicates == 0:
        print("\n[完成] 没有发现重复文件，程序结束。")
        return

    print(f"\n[发现] 共找到 {total_duplicates} 个重复文件（内容相同但名称不同）。")

    # 打印出所有重复的文件组，供用户查看
    print("\n📋 以下是检测到的重复文件组：\n")
    print("[提示] 程序会优先删除文件名中带有 '(1)' 或 '-副本' 的副本。")
    for idx, (hash_val, file_list) in enumerate(duplicates.items()):
        print(f"【组 {idx + 1}】以下文件内容相同：")
        for file_path in file_list:
            print(f"  → {file_path}")
        print("-" * 60)

    # 用户选择删除模式
    print("\n请选择删除模式：")
    print("1. 输入 'delete-all' 或 '1' 自动删除所有重复文件")
    print("2. 输入 'delete-by-group' 或 '2' 分组确认删除")
    print("3. 输入其他内容取消操作")
    choice = input("请输入您的选择: ").strip().lower()

    if choice in ['delete-all', '1']:
        delete_mode = 'all'
    elif choice in ['delete-by-group', '2']:
        delete_mode = 'group'
    else:
        print("[操作取消] 用户中断操作，未删除任何文件。")
        return

    # 开始删除
    deleted_count = 0
    failed_files = []

    print("\n[删除] 开始删除重复文件...\n")

    for idx, (hash_val, file_list) in enumerate(duplicates.items()):
        # 排序：副本标识排后面，保留第一个“非副本”文件
        file_list.sort(key=lambda x: (is_duplicate_indicator_in_filename(x), x))
        candidates = file_list.copy()  # 复制一份用于删除
        keep_file = candidates.pop(0)  # 取第一个作为保留文件

        if delete_mode == 'group':
            print("\n当前组重复文件：")
            for i, file in enumerate(candidates):
                print(f"  {i+1}. {file}")
            confirm_group = input(f"确定要删除这 {len(candidates)} 个重复文件吗？(y/n): ").strip().lower()
            if confirm_group != 'y':
                print("跳过此组重复文件。")
                continue

        elif delete_mode == 'all' and idx == 0:
            print("\n⚠️ 警告：此操作将永久删除重复文件，请确保已备份重要数据。")
            confirm = input("确定要删除重复文件吗？请输入 yes 以继续，其他任意键取消: ").strip().lower()
            if confirm != 'yes':
                print("[操作取消] 用户中断操作，未删除任何文件。")
                return

        # 删除副本
        for i, file in enumerate(candidates):
            print(f"\r正在删除第 {i+1}/{len(candidates)} 个副本: {os.path.basename(file)}", end="")
            success = delete_file(file)
            if success:
                deleted_count += 1
            else:
                failed_files.append(file)
        print()

    # 输出结果
    print("\n=== 清理完成 ===")
    print(f"成功删除文件数：{deleted_count}")
    if failed_files:
        print(f"未能删除的文件数：{len(failed_files)}")
        for f in failed_files:
            print(f" - {f}")

    print("\n程序即将退出...")

if __name__ == "__main__":
    try:
        main()
    finally:
        print("\n[进程结束] 程序已终止。")
        input("按任意键退出...")
        sys.exit(0)