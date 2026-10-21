import os
import sys
from pathlib import Path

# 添加 backend 到路径
sys.path.append(str(Path(__file__).resolve().parent.parent / "backend"))

from memory_manager import MemoryManager
from os_tools import OSTools
from agent_brain import AgentBrain

def run_tests():
    mem = MemoryManager()
    tools = OSTools(mem)
    brain = AgentBrain(mem, tools)

    print("=== 开始测试命令行与文件工具 ===")

    # 1. 测试 execute_command
    res1 = tools.execute_command("echo 'Terminal Command Works!'")
    print("[Test 1 execute_command]:", res1["output"].strip())
    assert res1["success"] is True
    assert "Terminal Command Works!" in res1["output"]

    # 2. 测试 modify_file 创建并写入文件
    test_file = "help/sample_test_file.txt"
    content = "Hello Jarvis!\nLine 2: OS Agent Terminal Tool.\nLine 3: File Modification Succeeded."
    res2 = tools.modify_file(test_file, content, mode="overwrite")
    print("[Test 2 modify_file]:", res2["message"])
    assert res2["success"] is True

    # 3. 测试 read_file 读取文件
    res3 = tools.read_file(test_file, start_line=1, line_count=10)
    print("[Test 3 read_file]:\n", res3["message"])
    assert res3["success"] is True
    assert "Line 2: OS Agent Terminal Tool." in res3["content"]

    # 4. 测试通过 execute_command 读取刚才的文件 (cat)
    res4 = tools.execute_command(f"cat {test_file}")
    print("[Test 4 execute_command cat]:\n", res4["output"])
    assert res4["success"] is True
    assert "Hello Jarvis!" in res4["output"]

    # 5. 测试高危命令拦截
    res5 = tools.execute_command("rm -rf /")
    print("[Test 5 Dangerous Command Guard]:", res5["message"])
    assert res5["success"] is False
    assert "安全拦截" in res5["message"]

    # 6. 测试语义路由：查看文件
    res6 = brain._fallback_intent_router(f"查看文件 {test_file}")
    print("[Test 6 Router read_file]:", res6)
    assert res6 is not None and res6["tool"] == "read_file"

    # 7. 测试语义路由：执行命令
    res7 = brain._fallback_intent_router("执行命令 git status -s")
    print("[Test 7 Router execute_command]:", res7)
    assert res7 is not None and res7["tool"] == "execute_command"

    # 8. 测试 process_query 处理文件查看
    res8 = brain.process_query(f"查看文件 {test_file}")
    print("[Test 8 process_query read_file reply]:\n", res8["reply"])
    assert res8["tool_call"] is not None
    assert res8["tool_call"]["name"] == "read_file"

    # 9. 测试 process_query 执行命令
    res9 = brain.process_query("执行命令 echo 'Jarvis Command Line Ready'")
    print("[Test 9 process_query execute_command reply]:\n", res9["reply"])
    assert res9["tool_call"] is not None
    assert res9["tool_call"]["name"] == "execute_command"

    # 清理测试辅助文件
    if Path(test_file).exists():
        os.remove(test_file)

    print("\n✅ 所有的命令行与文件操作工具测试全部成功通过！")

if __name__ == "__main__":
    run_tests()
