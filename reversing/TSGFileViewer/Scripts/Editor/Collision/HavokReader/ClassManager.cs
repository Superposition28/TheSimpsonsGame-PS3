using System;
using System.Collections.Generic;
using Editor.Collision.HavokReader.Classes;
using UnityEngine;

namespace Editor.Collision.HavokReader
{
	public class ClassManager
	{
		public static Dictionary<string, Type> ClassMap = new Dictionary<string, Type>()
		{
			{ "hkBoxShape", typeof(hkBoxShape) },
			{ "hkSpatialRigidBodyDeactivator", typeof(hkSpatialRigidBodyDeactivator) },
			{ "EAStorageMeshShape", typeof(EAStorageMeshShape)}
		};

		public static HavokClass GetClass(string name)
		{
			Type sectionType;
			if (ClassMap.TryGetValue(name, out var value))
			{
				sectionType = value;
			}
			else
			{
				Debug.LogWarning($"Could not find class definition for [{name}]");
				sectionType = typeof(UnknownClass);
			}

			var instance = (HavokClass)Activator.CreateInstance(sectionType);
			return instance;
		}
	}
}
