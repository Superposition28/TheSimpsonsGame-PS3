using System;
using System.IO;
using UnityEditor;
using UnityEngine;

[CustomPropertyDrawer(typeof(RwMatrixTag))]
public class RwMatrixTagDrawer : PropertyDrawer
{
	public override void OnGUI(Rect position, SerializedProperty property, GUIContent label)
	{
		EditorGUI.BeginProperty(position, label, property);

		position = EditorGUI.PrefixLabel(position, GUIUtility.GetControlID(FocusType.Passive), label);

		var indent = EditorGUI.indentLevel;
		EditorGUI.indentLevel = 0;

		var cellWidth = position.width / 4f;

		string[] vecNames = { "Right", "Up", "At", "Pos" };
		string[] padNames = { "Pad0", "Pad1", "Pad2", "Pad3" };

		for (var y = 0; y < 4; y++)
		{
			var vecProp = property.FindPropertyRelative(vecNames[y]);
			var padProp = property.FindPropertyRelative(padNames[y]);

			for (var x = 0; x < 4; x++)
			{
				var cellRect = new Rect(
					position.x + x * cellWidth,
					position.y + y * (EditorGUIUtility.singleLineHeight + 2),
					cellWidth - 2,
					EditorGUIUtility.singleLineHeight
				);

				if (x < 3)
				{
					var component = vecProp.FindPropertyRelative("x");
					switch (x)
					{
						case 1:
							component = vecProp.FindPropertyRelative("y");
							break;
						case 2:
							component = vecProp.FindPropertyRelative("z");
							break;
					}

					component.floatValue = EditorGUI.FloatField(cellRect, GUIContent.none, component.floatValue);
				}
				else
				{
					padProp.floatValue = EditorGUI.FloatField(cellRect, GUIContent.none, padProp.floatValue);
				}
			}
		}

		EditorGUI.indentLevel = indent;
		EditorGUI.EndProperty();
	}

	public override float GetPropertyHeight(SerializedProperty property, GUIContent label)
	{
		return (EditorGUIUtility.singleLineHeight + 2) * 4;
	}
}

[Serializable]
public class RwMatrixTag
{
	public Vector3 Right;
	public float Pad0;

	public Vector3 Up;
	public float Pad1;

	public Vector3 At;
	public float Pad2;

	public Vector3 Pos;
	public float Pad3;

	public RwMatrixTag(BinaryReader reader)
	{
		Right = reader.ReadRwV3d();
		Pad0 = reader.ReadSingleBigEndian();

		Up = reader.ReadRwV3d();
		Pad1 = reader.ReadSingleBigEndian();

		At = reader.ReadRwV3d();
		Pad2 = reader.ReadSingleBigEndian();

		Pos = reader.ReadRwV3d();
		Pad3 = reader.ReadSingleBigEndian();
	}

	public (Vector3 position, Quaternion rotation, Vector3 scale) GetTRS()
	{
		var position = new Vector3(Pos.x, Pos.y, -Pos.z);
		var scale = new Vector3(Right.magnitude, Up.magnitude, At.magnitude);

		var right = Right;
		var up = Up;
		var forward = -At;

		right.Normalize();
		up.Normalize();
		forward.Normalize();

		right.z = -right.z;
		up.z = -up.z;
		forward.z = -forward.z;

		// sanity checking
		right = Vector3.Cross(up, forward).normalized;
		up = Vector3.Cross(forward, right).normalized;

		var rotation = Quaternion.LookRotation(forward, up);

		return (position, rotation, scale);
	}
}