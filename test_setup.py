"""Test suite for verifying the ADK and A2A Weather and Itinerary Planner setup."""

import json
import os
import sys

# Ensure current working directory is in PYTHONPATH
sys.path.insert(0, os.path.abspath("."))

def run_tests():
    print("=" * 60)
    print("RUNNING ADK & A2A LAB COMPONENT TESTS")
    print("=" * 60)

    # ----------------------------------------------------
    # Test 1: Weather Agent ADK Definition & Google Search Grounding
    # ----------------------------------------------------
    print("\n[TEST 1] Testing Weather Agent Definition & Google Search Grounding...")
    try:
        from weather_agent.agent import root_agent
        assert root_agent.name == "weather_agent"
        assert root_agent.model == "gemini-3.8-flash"
        assert len(root_agent.tools) == 1
        assert root_agent.tools[0].name == "google_search"
        print(f"  ✓ Weather agent loaded successfully: name='{root_agent.name}', model='{root_agent.model}'.")
        print(f"  ✓ Google Search Grounding tool configured: {[t.name for t in root_agent.tools]}.")
    except Exception as e:
        print(f"  ✗ Failed loading Weather Agent: {e}")
        return False

    # ----------------------------------------------------
    # Test 2: Weather Agent Prompt Rules & Output Specs
    # ----------------------------------------------------
    print("\n[TEST 2] Testing Weather Agent Prompt Instructions...")
    try:
        instruction = root_agent.instruction.lower()
        assert "temperature" in instruction
        assert "precipitation" in instruction
        assert "google_search" in instruction
        print("  ✓ Weather agent instructions include temperature, precipitation, and search grounding.")
    except Exception as e:
        print(f"  ✗ Failed validating weather agent instructions: {e}")
        return False

    # ----------------------------------------------------
    # Test 3: Explicit Agent Card (agent.json) Validation
    # ----------------------------------------------------
    print("\n[TEST 3] Validating Agent Card (agent.json)...")
    try:
        agent_card_file = os.path.join("weather_agent", "agent.json")
        assert os.path.exists(agent_card_file), "agent.json does not exist"
        with open(agent_card_file, "r") as f:
            card_data = json.load(f)
        assert card_data["name"] == "weather_agent"
        assert "skills" in card_data
        assert any(s["id"] == "get_current_weather" for s in card_data["skills"])
        print("  ✓ Agent Card exists and has valid name, capabilities, and skills.")
    except Exception as e:
        print(f"  ✗ Failed validating agent.json: {e}")
        return False

    # ----------------------------------------------------
    # Test 4: A2A ASGI Server Application & Well-Known Endpoint
    # ----------------------------------------------------
    print("\n[TEST 4] Testing A2A ASGI Application and Agent Card Endpoint...")
    try:
        from starlette.testclient import TestClient
        from weather_agent.main import app

        with TestClient(app) as client:
            response = client.get("/.well-known/agent.json")
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            card_response = response.json()
            assert card_response.get("name") == "weather_agent"
            print(f"  ✓ GET /.well-known/agent.json returned HTTP 200 OK:")
            print(f"    - Agent Name: {card_response.get('name')}")
            print(f"    - Description: {card_response.get('description')[:60]}...")
            print(f"    - Skills Advertised: {[s['id'] for s in card_response.get('skills', [])]}")
    except Exception as e:
        print(f"  ✗ Failed testing A2A server endpoint: {e}")
        return False

    # ----------------------------------------------------
    # Test 5: Itinerary Planner Specialist Agent
    # ----------------------------------------------------
    print("\n[TEST 5] Testing Itinerary Planner Specialist Agent...")
    try:
        from itinerary_planner.agent import itinerary_planner

        assert itinerary_planner.name == "itinerary_planner"
        assert "umbrella" in itinerary_planner.instruction.lower()

        print(f"  ✓ Itinerary Planner loaded successfully: name='{itinerary_planner.name}'.")
        print("  ✓ Umbrella prompt rule verified in agent instructions.")
    except Exception as e:
        print(f"  ✗ Failed testing Itinerary Planner Agent: {e}")
        return False

    # ----------------------------------------------------
    # Test 6: Root Agent (Travel Concierge) Handling Both Agents as AgentTools
    # ----------------------------------------------------
    print("\n[TEST 6] Testing Root Agent (Travel Concierge) Coordinating Both Agents as Tools...")
    try:
        from travel_concierge.agent import root_agent as concierge_root
        from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
        from google.adk.tools import AgentTool

        assert concierge_root.name == "travel_concierge"
        assert len(concierge_root.tools) == 2

        tool_names = [t.name for t in concierge_root.tools]
        assert "weather_agent" in tool_names, "weather_agent missing from tools"
        assert "itinerary_planner" in tool_names, "itinerary_planner missing from tools"

        weather_tool = next(t for t in concierge_root.tools if t.name == "weather_agent")
        assert isinstance(weather_tool, AgentTool), "weather_agent tool is not an AgentTool"
        assert isinstance(weather_tool.agent, RemoteA2aAgent), "weather_agent tool's agent is not a RemoteA2aAgent"

        planner_tool = next(t for t in concierge_root.tools if t.name == "itinerary_planner")
        assert isinstance(planner_tool, AgentTool), "itinerary_planner tool is not an AgentTool"

        print(f"  ✓ Root Agent loaded successfully: name='{concierge_root.name}'.")
        print(f"  ✓ Specialist agents coordinated as tools: {tool_names}.")
        print("  ✓ Weather agent correctly configured as RemoteA2aAgent proxy via AgentTool.")
        print("  ✓ Itinerary planner correctly configured as local specialist via AgentTool.")
    except Exception as e:
        print(f"  ✗ Failed testing Root Agent: {e}")
        return False

    print("\n" + "=" * 60)
    print("ALL 6 COMPONENT AND PROTOCOL TESTS PASSED SUCCESSFULLY! 🎉")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
