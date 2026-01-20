def format_world_state_for_display(world_state: dict) -> str:
    """world_stateを人間が読みやすい形式の文字列に変換する"""
    pose = world_state.get('kachaka_pose')
    pose_str = f"(x={pose['x']:.2f}, y={pose['y']:.2f}, θ={pose['theta']:.2f})" if pose else "N/A"
    
    formatted_string = (
        f"  - Akari location: {world_state['akari_location']}\n"
        f"  - Kachaka location: {world_state['kachaka_location']} {pose_str}\n"
        f"  - Docked with: {world_state['docked_with']}\n"
    )
    if world_state.get('obstacle'):
        obs = world_state['obstacle']
        coords = obs.get('coords', {})
        x_val = coords.get('x_world', 'N/A')
        y_val = coords.get('y_world', 'N/A')
        x_str = f"{x_val:.2f}" if isinstance(x_val, (int, float)) else str(x_val)
        y_str = f"{y_val:.2f}" if isinstance(y_val, (int, float)) else str(y_val)
        coord_str = f"(x={x_str}, y={y_str})"
        formatted_string += f"  - Obstacle: id={obs.get('id')}, coords={coord_str}, cleared={obs.get('cleared')}"
    
    return formatted_string