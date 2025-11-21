#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接修改 final_xdp_manager.sh，添加编译、加载和全局执行时间监测
"""

# 读取原始文件
with open('final_xdp_manager.sh', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 在 print_debug 之后添加计时函数
new_lines = []
for i, line in enumerate(lines):
    new_lines.append(line)

    # 在 print_debug 行后添加计时函数
    if 'print_debug() { echo -e "${PURPLE}🐛 $1${NC}"; }' in line:
        new_lines.append('print_timer() { echo -e "${CYAN}⏱  $1${NC}"; }\n')
        new_lines.append('\n')
        new_lines.append('# 获取当前时间戳（毫秒）\n')
        new_lines.append('get_timestamp_ms() {\n')
        new_lines.append('    echo $(($(date +%s%N) / 1000000))\n')
        new_lines.append('}\n')
        new_lines.append('\n')
        new_lines.append('# 计算时间差\n')
        new_lines.append('calc_time_diff_ms() {\n')
        new_lines.append('    echo $(($2 - $1))\n')
        new_lines.append('}\n')
        new_lines.append('\n')
        new_lines.append('# 格式化时间\n')
        new_lines.append('format_time() {\n')
        new_lines.append('    local ms=$1\n')
        new_lines.append('    if [ $ms -lt 1000 ]; then\n')
        new_lines.append('        echo "${ms}ms"\n')
        new_lines.append('    else\n')
        new_lines.append('        echo "$(echo "scale=3; $ms/1000" | bc 2>/dev/null || echo 0)s"\n')
        new_lines.append('    fi\n')
        new_lines.append('}\n')
        new_lines.append('\n')

# 写入临时文件
with open('final_xdp_manager_modified.sh', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

# 修改 compile_xdp_program 函数，添加编译时间监测
with open('final_xdp_manager_modified.sh', 'r', encoding='utf-8') as f:
    content = f.read()

# 找到并替换 compile_xdp_program 函数
old_compile = '''# 编译XDP程序
compile_xdp_program() {
    local mac="$1"

    print_info "编译XDP程序..."

    # 如果有指定单个MAC地址，添加到列表
    if [ -n "$mac" ]; then
        add_mac_to_list "$mac"
    fi

    # 生成支持多个MAC的源码
    generate_xdp_source

    # 显示生成的源码前几行（用于调试）
    print_info "生成的源码预览:"
    head -25 "$PROGRAM_SOURCE"

    # 编译程序 - 使用您原来的编译命令
    print_info "编译命令: clang -O2 -target bpf -I /usr/include/x86_64-linux-gnu -c $PROGRAM_SOURCE -o $PROGRAM_OBJECT"

    if clang -O2 -target bpf -I /usr/include/x86_64-linux-gnu -c "$PROGRAM_SOURCE" -o "$PROGRAM_OBJECT" 2>&1; then
        print_success "XDP程序编译成功"
        return 0
    else
        print_error "XDP程序编译失败"
        # 显示详细错误信息
        clang -O2 -target bpf -I /usr/include/x86_64-linux-gnu -c "$PROGRAM_SOURCE" -o "$PROGRAM_OBJECT"
        return 1
    fi
}'''

new_compile = '''# 编译XDP程序
compile_xdp_program() {
    local mac="$1"

    local compile_start=$(get_timestamp_ms)
    print_info "编译XDP程序..."

    # 如果有指定单个MAC地址，添加到列表
    if [ -n "$mac" ]; then
        add_mac_to_list "$mac"
    fi

    # 生成支持多个MAC的源码
    local gen_start=$(get_timestamp_ms)
    generate_xdp_source
    local gen_end=$(get_timestamp_ms)
    print_timer "源码生成耗时: $(format_time $(calc_time_diff_ms $gen_start $gen_end))"

    # 显示生成的源码前几行（用于调试）
    print_info "生成的源码预览:"
    head -25 "$PROGRAM_SOURCE"

    # 编译程序 - 使用您原来的编译命令
    print_info "编译命令: clang -O2 -target bpf -I /usr/include/x86_64-linux-gnu -c $PROGRAM_SOURCE -o $PROGRAM_OBJECT"

    local clang_start=$(get_timestamp_ms)
    if clang -O2 -target bpf -I /usr/include/x86_64-linux-gnu -c "$PROGRAM_SOURCE" -o "$PROGRAM_OBJECT" 2>&1; then
        local clang_end=$(get_timestamp_ms)
        print_timer "编译耗时: $(format_time $(calc_time_diff_ms $clang_start $clang_end))"
        print_success "XDP程序编译成功"

        local compile_end=$(get_timestamp_ms)
        print_timer "编译阶段总耗时: $(format_time $(calc_time_diff_ms $compile_start $compile_end))"
        return 0
    else
        print_error "XDP程序编译失败"
        # 显示详细错误信息
        clang -O2 -target bpf -I /usr/include/x86_64-linux-gnu -c "$PROGRAM_SOURCE" -o "$PROGRAM_OBJECT"
        return 1
    fi
}'''

content = content.replace(old_compile, new_compile)

# 修改 load_xdp_program 函数，添加加载时间监测
old_load = '''# 加载XDP程序
load_xdp_program() {
    print_info "加载XDP程序到接口 $INTERFACE..."

    # 首先卸载可能存在的程序
    sudo ip link set dev "$INTERFACE" xdpgeneric off 2>/dev/null
    sudo ip link set dev "$INTERFACE" xdp off 2>/dev/null

    # 尝试加载程序 - 优先使用SKB模式
    if sudo ip link set dev "$INTERFACE" xdpgeneric obj "$PROGRAM_OBJECT" sec xdp 2>/dev/null; then
        print_success "XDP程序加载成功（SKB模式）"
        return 0
    else
        print_warning "SKB模式加载失败，尝试Native模式..."
        if sudo ip link set dev "$INTERFACE" xdp obj "$PROGRAM_OBJECT" sec xdp 2>/dev/null; then
            print_success "XDP程序加载成功（Native模式）"
            return 0
        else
            print_error "XDP程序加载失败"
            return 1
        fi
    fi
}'''

new_load = '''# 加载XDP程序
load_xdp_program() {
    local load_start=$(get_timestamp_ms)
    print_info "加载XDP程序到接口 $INTERFACE..."

    # 首先卸载可能存在的程序
    local unload_start=$(get_timestamp_ms)
    sudo ip link set dev "$INTERFACE" xdpgeneric off 2>/dev/null
    sudo ip link set dev "$INTERFACE" xdp off 2>/dev/null
    local unload_end=$(get_timestamp_ms)
    print_timer "卸载旧程序耗时: $(format_time $(calc_time_diff_ms $unload_start $unload_end))"

    # 尝试加载程序 - 优先使用SKB模式
    local attach_start=$(get_timestamp_ms)
    if sudo ip link set dev "$INTERFACE" xdpgeneric obj "$PROGRAM_OBJECT" sec xdp 2>/dev/null; then
        local attach_end=$(get_timestamp_ms)
        print_timer "挂载程序耗时: $(format_time $(calc_time_diff_ms $attach_start $attach_end))"
        print_success "XDP程序加载成功（SKB模式）"

        local load_end=$(get_timestamp_ms)
        print_timer "加载阶段总耗时: $(format_time $(calc_time_diff_ms $load_start $load_end))"
        return 0
    else
        print_warning "SKB模式加载失败，尝试Native模式..."
        local native_start=$(get_timestamp_ms)
        if sudo ip link set dev "$INTERFACE" xdp obj "$PROGRAM_OBJECT" sec xdp 2>/dev/null; then
            local native_end=$(get_timestamp_ms)
            print_timer "挂载程序耗时: $(format_time $(calc_time_diff_ms $native_start $native_end))"
            print_success "XDP程序加载成功（Native模式）"

            local load_end=$(get_timestamp_ms)
            print_timer "加载阶段总耗时: $(format_time $(calc_time_diff_ms $load_start $load_end))"
            return 0
        else
            print_error "XDP程序加载失败"
            return 1
        fi
    fi
}'''

content = content.replace(old_load, new_load)

# 修改 start_filter 函数，添加全局时间监测
old_start = '''# 启动过滤
start_filter() {
    local mac="$1"

    # 检查依赖和接口
    check_dependencies || return 1
    check_interface || return 1

    # 初始化MAC列表
    init_mac_list

    # 如果有指定MAC地址，添加到列表
    if [ -n "$mac" ]; then
        add_mac_to_list "$mac"
    fi

    # 检查是否有MAC地址需要过滤
    if [ ! -s "$MAC_LIST_FILE" ]; then
        print_warning "MAC地址列表为空，将不会过滤任何流量"
        print_info "使用 'addmac' 命令添加MAC地址，例如: $0 addmac 00:11:22:33:44:55"
    fi

    # 编译程序
    compile_xdp_program || return 1

    # 加载程序
    load_xdp_program || return 1

    # 保存配置
    save_config "$mac"

    print_success "XDP MAC地址过滤已启动"
    show_status
}'''

new_start = '''# 启动过滤
start_filter() {
    local mac="$1"

    local global_start=$(get_timestamp_ms)
    echo ""
    print_timer "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_timer "开始启动XDP过滤程序"
    print_timer "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # 检查依赖和接口
    local check_start=$(get_timestamp_ms)
    check_dependencies || return 1
    check_interface || return 1
    local check_end=$(get_timestamp_ms)
    print_timer "依赖和接口检查耗时: $(format_time $(calc_time_diff_ms $check_start $check_end))"
    echo ""

    # 初始化MAC列表
    init_mac_list

    # 如果有指定MAC地址，添加到列表
    if [ -n "$mac" ]; then
        add_mac_to_list "$mac"
    fi

    # 检查是否有MAC地址需要过滤
    if [ ! -s "$MAC_LIST_FILE" ]; then
        print_warning "MAC地址列表为空，将不会过滤任何流量"
        print_info "使用 'addmac' 命令添加MAC地址，例如: $0 addmac 00:11:22:33:44:55"
    fi

    # 编译程序
    echo ""
    print_info "━━━ 编译阶段 ━━━"
    compile_xdp_program || return 1

    # 加载程序
    echo ""
    print_info "━━━ 加载阶段 ━━━"
    load_xdp_program || return 1

    # 保存配置
    save_config "$mac"

    local global_end=$(get_timestamp_ms)
    echo ""
    print_timer "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_timer "全局执行总耗时: $(format_time $(calc_time_diff_ms $global_start $global_end))"
    print_timer "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    print_success "XDP MAC地址过滤已启动"
    show_status
}'''

content = content.replace(old_start, new_start)

# 修改 addmac 添加全局时间
old_addmac = '''# 添加MAC地址到列表
add_mac_to_list() {
    local mac="$1"

    if [ -z "$mac" ]; then
        print_error "需要指定要添加的MAC地址"
        return 1
    fi

    # 验证MAC地址格式
    local mac_c_format
    mac_c_format=$(validate_and_convert_mac "$mac")
    if [ $? -ne 0 ]; then
        return 1
    fi

    init_mac_list

    local standard_mac=$(convert_to_standard_mac "$mac_c_format")

    # 检查是否已存在
    if grep -q "^$standard_mac$" "$MAC_LIST_FILE"; then
        print_warning "MAC地址 $standard_mac 已存在于列表中"
        return 0
    fi

    # 添加到文件
    echo "$standard_mac" >> "$MAC_LIST_FILE"
    print_success "MAC地址 $standard_mac 已添加到过滤列表"

    # 如果XDP程序正在运行，重新加载
    if ip link show dev "$INTERFACE" | grep -q "prog/xdp"; then
        print_info "XDP程序正在运行，重新加载以应用更改..."
        reload_xdp_program
    fi
}'''

new_addmac = '''# 添加MAC地址到列表
add_mac_to_list() {
    local mac="$1"

    local global_start=$(get_timestamp_ms)
    echo ""
    print_timer "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_timer "开始添加MAC地址: $mac"
    print_timer "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if [ -z "$mac" ]; then
        print_error "需要指定要添加的MAC地址"
        return 1
    fi

    # 验证MAC地址格式
    local step1_start=$(get_timestamp_ms)
    local mac_c_format
    mac_c_format=$(validate_and_convert_mac "$mac")
    if [ $? -ne 0 ]; then
        return 1
    fi
    local step1_end=$(get_timestamp_ms)
    print_timer "1. MAC地址格式验证: $(format_time $(calc_time_diff_ms $step1_start $step1_end))"

    local step2_start=$(get_timestamp_ms)
    init_mac_list
    local step2_end=$(get_timestamp_ms)
    print_timer "2. 初始化MAC列表: $(format_time $(calc_time_diff_ms $step2_start $step2_end))"

    local step3_start=$(get_timestamp_ms)
    local standard_mac=$(convert_to_standard_mac "$mac_c_format")
    local step3_end=$(get_timestamp_ms)
    print_timer "3. 转换为标准格式: $(format_time $(calc_time_diff_ms $step3_start $step3_end))"

    # 检查是否已存在
    local step4_start=$(get_timestamp_ms)
    if grep -q "^$standard_mac$" "$MAC_LIST_FILE"; then
        print_warning "MAC地址 $standard_mac 已存在于列表中"
        local global_end=$(get_timestamp_ms)
        print_timer "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_timer "总耗时: $(format_time $(calc_time_diff_ms $global_start $global_end))"
        print_timer "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        return 0
    fi
    local step4_end=$(get_timestamp_ms)
    print_timer "4. 检查重复: $(format_time $(calc_time_diff_ms $step4_start $step4_end))"

    # 添加到文件
    local step5_start=$(get_timestamp_ms)
    echo "$standard_mac" >> "$MAC_LIST_FILE"
    print_success "MAC地址 $standard_mac 已添加到过滤列表"
    local step5_end=$(get_timestamp_ms)
    print_timer "5. 写入文件: $(format_time $(calc_time_diff_ms $step5_start $step5_end))"

    # 如果XDP程序正在运行，重新加载
    if ip link show dev "$INTERFACE" | grep -q "prog/xdp"; then
        echo ""
        print_info "XDP程序正在运行，重新加载以应用更改..."
        reload_xdp_program
    fi

    local global_end=$(get_timestamp_ms)
    echo ""
    print_timer "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_timer "添加MAC地址总耗时: $(format_time $(calc_time_diff_ms $global_start $global_end))"
    print_timer "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
}'''

content = content.replace(old_addmac, new_addmac)

# 修改 reload_xdp_program 添加时间监测
old_reload = '''# 重新加载XDP程序
reload_xdp_program() {
    print_info "重新编译和加载XDP程序..."

    # 检查依赖和接口
    check_dependencies || return 1
    check_interface || return 1

    # 生成支持多个MAC的源码
    generate_xdp_source

    # 显示生成的源码前几行（用于调试）
    print_info "生成的源码预览:"
    head -25 "$PROGRAM_SOURCE"

    # 编译程序 - 使用您原来的编译命令
    print_info "编译XDP程序..."
    if clang -O2 -target bpf -I /usr/include/x86_64-linux-gnu -c "$PROGRAM_SOURCE" -o "$PROGRAM_OBJECT" 2>&1; then
        print_success "XDP程序编译成功"
    else
        print_error "XDP程序编译失败"
        # 显示详细错误信息
        clang -O2 -target bpf -I /usr/include/x86_64-linux-gnu -c "$PROGRAM_SOURCE" -o "$PROGRAM_OBJECT"
        return 1
    fi

    # 重新加载程序
    load_xdp_program
}'''

new_reload = '''# 重新加载XDP程序
reload_xdp_program() {
    local reload_start=$(get_timestamp_ms)
    print_info "重新编译和加载XDP程序..."

    # 检查依赖和接口
    check_dependencies || return 1
    check_interface || return 1

    # 生成支持多个MAC的源码
    local gen_start=$(get_timestamp_ms)
    generate_xdp_source
    local gen_end=$(get_timestamp_ms)
    print_timer "  源码生成: $(format_time $(calc_time_diff_ms $gen_start $gen_end))"

    # 显示生成的源码前几行（用于调试）
    print_info "生成的源码预览:"
    head -25 "$PROGRAM_SOURCE"

    # 编译程序 - 使用您原来的编译命令
    print_info "编译XDP程序..."
    local compile_start=$(get_timestamp_ms)
    if clang -O2 -target bpf -I /usr/include/x86_64-linux-gnu -c "$PROGRAM_SOURCE" -o "$PROGRAM_OBJECT" 2>&1; then
        local compile_end=$(get_timestamp_ms)
        print_timer "  编译耗时: $(format_time $(calc_time_diff_ms $compile_start $compile_end))"
        print_success "XDP程序编译成功"
    else
        print_error "XDP程序编译失败"
        # 显示详细错误信息
        clang -O2 -target bpf -I /usr/include/x86_64-linux-gnu -c "$PROGRAM_SOURCE" -o "$PROGRAM_OBJECT"
        return 1
    fi

    # 重新加载程序
    load_xdp_program

    local reload_end=$(get_timestamp_ms)
    print_timer "重新加载总耗时: $(format_time $(calc_time_diff_ms $reload_start $reload_end))"
}'''

content = content.replace(old_reload, new_reload)

# 写入最终文件
with open('final_xdp_manager.sh', 'w', encoding='utf-8') as f:
    f.write(content)

print("[OK] Successfully modified final_xdp_manager.sh")
print("[INFO] Added timing measurements for:")
print("  - compile_xdp_program: source generation + compilation time")
print("  - load_xdp_program: unload + attach time + total load time")
print("  - start_filter: global execution time with all stages")
print("  - add_mac_to_list: 5-step timing + reload if needed")
print("  - reload_xdp_program: generation + compilation + loading")
